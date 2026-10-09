#!/usr/bin/env bash
# Rodada mensal dos indices TR e IPCA-E do TRT 8.
#
# Chamado pelo timer pjecalc-indices.timer, que dispara nos dias 6, 7 e 8,
# de segunda a sexta. Quem decide que so uma dessas datas vale e o marcador
# de mes aqui embaixo: a primeira execucao do mes grava o mes nele e as
# seguintes saem na hora. O efeito e "dia 6, ou o primeiro dia util depois
# dele" sem precisar ensinar calendario ao systemd.
set -euo pipefail

PROJETO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PJECALC="${PJECALC_HOME:-$HOME/.local/share/pjecalc}"
ESTADO="${XDG_STATE_HOME:-$HOME/.local/state}/pjecalc-automacao"
MARCADOR="$ESTADO/ultima-rodada"
URL="http://localhost:9257/pjecalc/pages/principal.jsf"
MES_ATUAL="$(date +%Y-%m)"

mkdir -p "$ESTADO"

avisar() {  # titulo, corpo, urgencia
  notify-send -a "PJe-Calc" -u "${3:-normal}" "$1" "$2" 2>/dev/null || true
}

if [ "${1:-}" != "--forcar" ] && [ -f "$MARCADOR" ] && [ "$(cat "$MARCADOR")" = "$MES_ATUAL" ]; then
  echo "Rodada de $MES_ATUAL ja foi feita em $(stat -c %y "$MARCADOR" | cut -d. -f1). Nada a fazer."
  exit 0
fi

echo "=== Rodada mensal $MES_ATUAL — $(date '+%d/%m/%Y %H:%M:%S') ==="

# O servidor pode estar parado se a unidade nao estiver habilitada no login.
if ! curl -sf -o /dev/null --max-time 10 "$URL"; then
  echo ">> Subindo o PJe-Calc..."
  systemctl --user start pjecalc 2>/dev/null || "$PJECALC/pjecalc.sh" start
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null --max-time 5 "$URL" && break
    sleep 2
  done
fi

if ! curl -sf -o /dev/null --max-time 10 "$URL"; then
  echo "ERRO: o PJe-Calc nao respondeu em $URL"
  avisar "Indices TRT 8: falhou" "O PJe-Calc nao subiu. Veja: journalctl --user -u pjecalc-indices" critical
  exit 1
fi

# Conferencia de versao: nao interrompe a rodada, so avisa. Versao nova muda
# tabela e regra de calculo, e a instalacao velha continua entregando numero
# sem reclamar.
VERSAO_AVISO=""
set +e
SAIDA_VERSAO="$(python3 "$PROJETO/scripts/verificar-versao.py" 2>&1)"
STATUS_VERSAO=$?
set -e
echo "$SAIDA_VERSAO"
case "$STATUS_VERSAO" in
  0) ;;
  1) VERSAO_AVISO="$(echo "$SAIDA_VERSAO" | grep 'Versao nova' || true)" ;;
  *) VERSAO_AVISO="Nao foi possivel conferir se ha versao nova do PJe-Calc." ;;
esac

echo ">> Extraindo indices (sem janela)..."
cd "$PROJETO"
if PJECALC_FF_HEADLESS=1 .venv/bin/python -u busca_indices_rpa.py; then
  PASTA="$PROJETO/output/$(date +%d-%m-%Y)"
  RESUMO="$(ls -1 "$PASTA"/*.xlsx 2>/dev/null | xargs -r -n1 basename | tr '\n' ' ' || true)"
  echo "$MES_ATUAL" > "$MARCADOR"
  CORPO="$PASTA
$RESUMO"
  [ -n "$VERSAO_AVISO" ] && CORPO="$CORPO

$VERSAO_AVISO"
  avisar "Indices TRT 8: planilhas prontas" "$CORPO"
  echo "=== Fim: OK ==="
else
  avisar "Indices TRT 8: falhou" "A extracao nao terminou. Veja: journalctl --user -u pjecalc-indices" critical
  echo "=== Fim: FALHOU ==="
  exit 1
fi
