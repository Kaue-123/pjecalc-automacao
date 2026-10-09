#!/usr/bin/env bash
# Testes do pjecalc.sh — o lancador e o dono do endereco do PJe-Calc, entao
# quebrar `url` quebra o rodada-mensal.sh e o verificar-versao.py junto.
#
# Monta uma instalacao falsa: nenhum teste aqui sobe JVM.
set -uo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PASSOU=0; FALHOU=0

afirmar() { [ "$1" -eq 0 ] && { PASSOU=$((PASSOU+1)); echo "  ok   — $2"; } \
                           || { FALHOU=$((FALHOU+1)); echo "  FALHA— $2"; }; }

montar() {
  CENARIO="$(mktemp -d)"
  mkdir -p "$CENARIO/app/bin/servico" "$CENARIO/bin"
  cp "$RAIZ/scripts/pjecalc.sh" "$CENARIO/app/"
  printf 'PJECALC_TOKEN_SERVICOS=token-de-teste\n' > "$CENARIO/app/pjecalc.env"
  # dubles do java: o lancador so confere que sao executaveis
  mkdir -p "$CENARIO/jdk/bin"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$CENARIO/jdk/bin/java"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$CENARIO/jdk/bin/javac"
  printf '#!/usr/bin/env bash\nexit "${STUB_CURL:-0}"\n' > "$CENARIO/bin/curl"
  chmod +x "$CENARIO/jdk/bin"/* "$CENARIO/bin"/* "$CENARIO/app/pjecalc.sh"
  export PJECALC_JAVA_HOME="$CENARIO/jdk" PATH="$CENARIO/bin:$PATH"
  LANCADOR="$CENARIO/app/pjecalc.sh"
}
desmontar() { rm -rf "$CENARIO"; unset STUB_CURL PJECALC_PORTA PJECALC_TENTATIVAS; }

echo "== endereco =="
montar
URL="$("$LANCADOR" url)"
afirmar $([ "$URL" = "http://localhost:9257/pjecalc/pages/principal.jsf" ]; echo $?) \
  "url devolve o endereco padrao"
URL="$(PJECALC_PORTA=8080 "$LANCADOR" url)"
afirmar $([ "$URL" = "http://localhost:8080/pjecalc/pages/principal.jsf" ]; echo $?) \
  "url respeita PJECALC_PORTA"
desmontar

echo
echo "== espera =="
montar
"$LANCADOR" esperar > /dev/null 2>&1
afirmar $? "esperar sai com 0 quando o servidor responde"
desmontar

montar
export STUB_CURL=1 PJECALC_TENTATIVAS=1
"$LANCADOR" esperar > /dev/null 2>&1
afirmar $([ $? -ne 0 ]; echo $?) "esperar sai diferente de 0 quando nada responde"
desmontar

echo
echo "== estado e uso =="
montar
afirmar $("$LANCADOR" status 2>/dev/null | grep -q "parado"; echo $?) \
  "status diz 'parado' sem pid"
"$LANCADOR" comando-que-nao-existe > "$CENARIO/uso.txt" 2>&1
afirmar $([ $? -ne 0 ]; echo $?) "subcomando desconhecido sai com erro"
afirmar $(grep -q "uso:" "$CENARIO/uso.txt"; echo $?) "subcomando desconhecido mostra o uso"
afirmar $(grep -q "url" "$CENARIO/uso.txt"; echo $?) "o uso lista os subcomandos novos"
desmontar

echo
echo "== pjecalc.env ausente =="
CENARIO="$(mktemp -d)"; mkdir -p "$CENARIO/app"
cp "$RAIZ/scripts/pjecalc.sh" "$CENARIO/app/"; chmod +x "$CENARIO/app/pjecalc.sh"
"$CENARIO/app/pjecalc.sh" url > "$CENARIO/erro.txt" 2>&1
afirmar $([ $? -ne 0 ]; echo $?) "sem pjecalc.env o lancador recusa rodar"
afirmar $(grep -q "pjecalc.env" "$CENARIO/erro.txt"; echo $?) "e diz qual arquivo falta"
rm -rf "$CENARIO"

echo
echo "─────────────────────────────────"
echo "  $PASSOU passaram, $FALHOU falharam"
[ "$FALHOU" -eq 0 ]
