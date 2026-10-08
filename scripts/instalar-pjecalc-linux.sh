#!/usr/bin/env bash
# Instala o PJe-Calc Cidadao 2.16.0 no Linux.
#
# O TRT8 distribui so um .exe homologado para Windows, mas o instalador e um ZIP
# auto-extraivel e a aplicacao e Java puro (Tomcat 7 embarcado + banco H2), sem
# nenhuma biblioteca nativa fora do JRE que vem junto. Este script baixa, confere
# o MD5 publicado, extrai, descarta as partes Windows (JRE e Firefox Portable) e
# instala um JDK 8 no lugar.
set -euo pipefail

VERSAO="2.16.0"
URL="https://www.trt8.jus.br/sites/portal/files/roles/pje-calc/pjecalc-${VERSAO}-instalador-x64.exe"
MD5_ESPERADO="a3795d4074563ce36b39b209c2c6f207"
JAVA_VERSAO="temurin-8.0.504+1"
DESTINO="${PJECALC_HOME:-$HOME/.local/share/pjecalc}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for cmd in curl 7z md5sum mise; do
  command -v "$cmd" >/dev/null || { echo "Faltando: $cmd"; exit 1; }
done

echo ">> Baixando PJe-Calc Cidadao $VERSAO (270 MB)..."
curl -# -o "$TMP/instalador.exe" "$URL"

echo ">> Conferindo MD5..."
MD5_OBTIDO="$(md5sum "$TMP/instalador.exe" | cut -d' ' -f1)"
[ "$MD5_OBTIDO" = "$MD5_ESPERADO" ] || {
  echo "MD5 nao confere. esperado=$MD5_ESPERADO obtido=$MD5_OBTIDO"; exit 1; }

echo ">> Extraindo..."
7z x -y -o"$TMP/extraido" "$TMP/instalador.exe" >/dev/null

# Java 8 e obrigatorio: em Java 17/21 o JBoss Seam e o Drools quebram no
# encapsulamento de modulos (InaccessibleObjectException), mesmo com --add-opens.
echo ">> Instalando JDK 8 ($JAVA_VERSAO) via mise..."
mise install "java@$JAVA_VERSAO"

echo ">> Instalando em $DESTINO..."
mkdir -p "$DESTINO"
cp -r "$TMP/extraido/pjecalc-windows64-$VERSAO/." "$DESTINO/"

# O iniciarPjeCalc.bat carrega dois parametros que a aplicacao exige. Sao
# constantes que vem iguais em todo instalador oficial, nao credenciais do
# usuario — mas ficam fora do versionamento, extraidas aqui do proprio .bat.
BAT="$DESTINO/iniciarPjeCalc.bat"
TOKEN="$(grep -oP '(?<=-Dseguranca\.pjecalc\.tokenServicos=)[^ ]+' "$BAT" | head -1)"
CONTEXTO="$(grep -oP '(?<=-Dseguranca\.pjekz\.servico\.contexto=")[^"]+' "$BAT" | head -1)"
[ -n "$TOKEN" ] || { echo "Nao consegui extrair o tokenServicos de $BAT"; exit 1; }
cat > "$DESTINO/pjecalc.env" <<ENVEOF
PJECALC_TOKEN_SERVICOS=$TOKEN
PJECALC_SEGURANCA_CONTEXTO=${CONTEXTO:-https://pje.trtXX.jus.br/pje-seguranca}
ENVEOF
chmod 600 "$DESTINO/pjecalc.env"

# bin/jre e um JRE 8 para Windows e navegador/windows e um Firefox Portable:
# os dois so pesam (167 MB) e nao rodam aqui.
rm -rf "$DESTINO/bin/jre" "$DESTINO/navegador/windows" "$DESTINO"/*.bat

cp "$(dirname "$(readlink -f "$0")")/pjecalc.sh" "$DESTINO/pjecalc.sh"
chmod +x "$DESTINO/pjecalc.sh"

echo
echo "Pronto. Para usar:"
echo "  $DESTINO/pjecalc.sh start    # sobe em http://localhost:9257/pjecalc"
echo "  $DESTINO/pjecalc.sh status"
echo "  $DESTINO/pjecalc.sh stop"
