#!/usr/bin/env bash
# Testes do rodada-mensal.sh — a logica de decisao da automacao.
#
# Monta um projeto falso com dubles para tudo que toca o mundo (curl, systemctl,
# notify-send, o lancador, a extracao) e exercita os caminhos. Nenhum teste aqui
# sobe PJe-Calc nem abre navegador.
set -uo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PASSOU=0; FALHOU=0

reportar() {  # resultado, nome
  if [ "$1" = "ok" ]; then PASSOU=$((PASSOU+1)); echo "  ok   — $2"
  else FALHOU=$((FALHOU+1)); echo "  FALHA— $2"; fi
}

afirmar() {  # condicao_ja_avaliada, nome
  [ "$1" -eq 0 ] && reportar ok "$2" || reportar falha "$2"
}

# ─── cenario ────────────────────────────────────────────────────────────
# Variaveis que cada teste ajusta antes de chamar `rodar`:
#   STUB_CURL        0 = servidor responde | 1 = fora do ar
#   STUB_ESPERAR     0 = subiu             | 1 = nao subiu
#   STUB_VERSAO      codigo de saida do verificar-versao.py
#   STUB_EXTRACAO    0 = extraiu           | outro = falhou
#   STUB_PASTA       o caminho que a extracao diz ter escrito
montar() {
  CENARIO="$(mktemp -d)"
  export XDG_STATE_HOME="$CENARIO/estado"
  export PJECALC_HOME="$CENARIO/pjecalc"
  mkdir -p "$PJECALC_HOME" "$CENARIO/bin" "$CENARIO/projeto/scripts" "$CENARIO/projeto/.venv/bin"

  cp "$RAIZ/scripts/rodada-mensal.sh" "$CENARIO/projeto/scripts/"

  cat > "$PJECALC_HOME/pjecalc.sh" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  url)     echo "http://localhost:9257/pjecalc/pages/principal.jsf" ;;
  esperar) exit "${STUB_ESPERAR:-0}" ;;
  *)       exit 0 ;;
esac
EOF

  cat > "$CENARIO/bin/curl" <<'EOF'
#!/usr/bin/env bash
exit "${STUB_CURL:-0}"
EOF

  cat > "$CENARIO/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$CENARIO/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "$CENARIO/notificacoes.txt"
EOF

  cat > "$CENARIO/projeto/scripts/verificar-versao.py" <<'EOF'
import os, sys
cod = int(os.environ.get("STUB_VERSAO", "0"))
print({0: "[ OK] PJe-Calc esta na versao atual.",
       1: "[AVS] Versao nova do PJe-Calc Cidadao: 9.9.9, desde 01/01/2027.",
       2: "[ERR] Nao consegui consultar o portal."}[cod])
sys.exit(cod)
EOF

  cat > "$CENARIO/projeto/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
pasta="${STUB_PASTA:?}"
mkdir -p "$pasta"
touch "$pasta/indices_TR_TRT8.xlsx" "$pasta/indices_IPCAE_TRT8.xlsx"
echo "  CONCLUIDO"
echo "  Pasta : $pasta"
exit "${STUB_EXTRACAO:-0}"
EOF

  chmod +x "$PJECALC_HOME/pjecalc.sh" "$CENARIO"/bin/* "$CENARIO/projeto/.venv/bin/python"
  export CENARIO PATH="$CENARIO/bin:$PATH"
  export STUB_PASTA="$CENARIO/projeto/output/01-01-2027"
}

desmontar() { rm -rf "$CENARIO"; unset STUB_CURL STUB_ESPERAR STUB_VERSAO STUB_EXTRACAO STUB_PASTA; }

rodar() { "$CENARIO/projeto/scripts/rodada-mensal.sh" "$@" > "$CENARIO/saida.txt" 2>&1; echo $?; }

marcar_mes_atual() {
  mkdir -p "$XDG_STATE_HOME/pjecalc-automacao"
  date +%Y-%m > "$XDG_STATE_HOME/pjecalc-automacao/ultima-rodada"
}

marcador() { cat "$XDG_STATE_HOME/pjecalc-automacao/ultima-rodada" 2>/dev/null; }
notificacoes() { cat "$CENARIO/notificacoes.txt" 2>/dev/null; }

# ─── testes ─────────────────────────────────────────────────────────────
echo "== guarda de uma rodada por mes =="

montar; marcar_mes_atual
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "mes ja feito: sai com 0"
afirmar $(grep -q "Nada a fazer" "$CENARIO/saida.txt"; echo $?) "mes ja feito: diz que nao ha o que fazer"
afirmar $([ -z "$(notificacoes)" ]; echo $?) "mes ja feito: nao notifica"
afirmar $([ ! -d "$STUB_PASTA" ]; echo $?) "mes ja feito: nao chama a extracao"
desmontar

montar; marcar_mes_atual
COD=$(rodar --forcar)
afirmar $([ "$COD" = "0" ]; echo $?) "--forcar ignora o marcador"
afirmar $([ -d "$STUB_PASTA" ]; echo $?) "--forcar chega a extrair"
desmontar

montar
mkdir -p "$XDG_STATE_HOME/pjecalc-automacao"
echo "2020-01" > "$XDG_STATE_HOME/pjecalc-automacao/ultima-rodada"
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "marcador de outro mes nao bloqueia"
afirmar $([ "$(marcador)" = "$(date +%Y-%m)" ]; echo $?) "marcador e atualizado para o mes corrente"
desmontar

echo
echo "== caminho feliz =="

montar
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "rodada completa sai com 0"
afirmar $([ "$(marcador)" = "$(date +%Y-%m)" ]; echo $?) "grava o marcador do mes"
afirmar $(notificacoes | grep -q "planilhas prontas"; echo $?) "notifica sucesso"
afirmar $(notificacoes | grep -q "01-01-2027"; echo $?) "a pasta da notificacao vem da saida da extracao"
afirmar $(notificacoes | grep -q "indices_TR_TRT8.xlsx"; echo $?) "lista as planilhas geradas"
desmontar

echo
echo "== a pasta e a que o Python disse, nao a que o shell adivinharia =="

montar
export STUB_PASTA="$CENARIO/projeto/output/31-12-1999"
COD=$(rodar)
afirmar $(notificacoes | grep -q "31-12-1999"; echo $?) "shell usa a pasta informada, mesmo com data improvavel"
afirmar $(! notificacoes | grep -q "$(date +%d-%m-%Y)"; echo $?) "shell nao recalcula a data por conta propria"
desmontar

echo
echo "== falhas =="

montar; export STUB_EXTRACAO=1
COD=$(rodar)
afirmar $([ "$COD" = "1" ]; echo $?) "extracao falhou: sai com 1"
afirmar $([ -z "$(marcador)" ]; echo $?) "extracao falhou: NAO grava o marcador (mes continua pendente)"
afirmar $(notificacoes | grep -q "falhou"; echo $?) "extracao falhou: notifica"
afirmar $(notificacoes | grep -q "critical"; echo $?) "extracao falhou: notificacao e critica"
desmontar

montar; export STUB_CURL=1 STUB_ESPERAR=1
COD=$(rodar)
afirmar $([ "$COD" = "1" ]; echo $?) "servidor nao sobe: sai com 1"
afirmar $(notificacoes | grep -q "nao subiu"; echo $?) "servidor nao sobe: diz o motivo"
afirmar $([ ! -d "$STUB_PASTA" ]; echo $?) "servidor nao sobe: nao tenta extrair"
desmontar

montar; export STUB_CURL=1 STUB_ESPERAR=0
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "servidor estava parado mas subiu: segue a rodada"
desmontar

echo
echo "== aviso de versao entra na notificacao =="

montar; export STUB_VERSAO=1
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "versao nova nao interrompe a rodada"
afirmar $(notificacoes | grep -q "Versao nova"; echo $?) "versao nova aparece na notificacao"
desmontar

montar; export STUB_VERSAO=2
COD=$(rodar)
afirmar $([ "$COD" = "0" ]; echo $?) "falha ao verificar versao nao interrompe a rodada"
afirmar $(notificacoes | grep -q "Nao foi possivel conferir"; echo $?) "falha ao verificar aparece na notificacao"
desmontar

montar; export STUB_VERSAO=0
COD=$(rodar)
afirmar $(! notificacoes | grep -qi "versao"; echo $?) "versao em dia nao polui a notificacao"
desmontar

echo
echo "─────────────────────────────────"
echo "  $PASSOU passaram, $FALHOU falharam"
[ "$FALHOU" -eq 0 ]
