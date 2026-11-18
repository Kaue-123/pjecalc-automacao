#!/usr/bin/env bash
# Rodada mensal dos indices TR e IPCA-E do TRT 8.
#
# O timer dispara nos dias 6, 7 e 8 (ver pjecalc-indices.timer); o marcador de
# mes aqui embaixo e que faz so a primeira dessas datas valer.
set -euo pipefail

PROJETO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PJECALC="${PJECALC_HOME:-$HOME/.local/share/pjecalc}"
LANCADOR="$PJECALC/pjecalc.sh"
ESTADO="${XDG_STATE_HOME:-$HOME/.local/state}/pjecalc-automacao"
MARCADOR="$ESTADO/ultima-rodada"
MES_ATUAL="$(date +%Y-%m)"
# O lancador e o dono do endereco; os filhos herdam por PJECALC_URL.
export PJECALC_URL="$("$LANCADOR" url)"

mkdir -p "$ESTADO"

# O aviso sempre fica registrado em arquivo e no journal. O canal externo e
# extra: notify-send so existe em sessao grafica, e num servidor sumiria calado
# justamente no caso que importa, que e o de falha.
avisar() {  # titulo, corpo, urgencia
  local titulo="$1" corpo="$2" urgencia="${3:-normal}"
  printf '%s\n[%s] %s\n%s\n' "$(date '+%d/%m/%Y %H:%M:%S')" "$urgencia" "$titulo" "$corpo" \
    > "$ESTADO/ultimo-aviso"
  echo "AVISO [$urgencia] $titulo"
  echo "$corpo" | sed 's/^/       /'

  if [ -n "${PJECALC_AVISO_CMD:-}" ]; then
    PJECALC_AVISO_TITULO="$titulo" PJECALC_AVISO_CORPO="$corpo" \
    PJECALC_AVISO_URGENCIA="$urgencia" sh -c "$PJECALC_AVISO_CMD" \
      || echo "AVISO: o canal externo PJECALC_AVISO_CMD falhou"
  elif [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ] && command -v notify-send > /dev/null; then
    notify-send -a "PJe-Calc" -u "$urgencia" "$titulo" "$corpo" || true
  fi
}

falhar() {
  avisar "Indices TRT 8: falhou" "$1
Veja: journalctl --user -u pjecalc-indices" critical
  echo "=== Fim: FALHOU ==="
  exit 1
}

if [ "${1:-}" != "--forcar" ] && [ -f "$MARCADOR" ] && [ "$(cat "$MARCADOR")" = "$MES_ATUAL" ]; then
  echo "Rodada de $MES_ATUAL ja foi feita em $(stat -c %y "$MARCADOR" | cut -d. -f1). Nada a fazer."
  exit 0
fi

echo "=== Rodada mensal $MES_ATUAL — $(date '+%d/%m/%Y %H:%M:%S') ==="

if ! curl -sf -o /dev/null --max-time 10 "$PJECALC_URL"; then
  echo ">> Subindo o PJe-Calc..."
  systemctl --user start pjecalc 2>/dev/null || true
  "$LANCADOR" esperar || falhar "O PJe-Calc nao subiu."
fi

# So avisa, nao interrompe a rodada — ver verificar-versao.py.
SAIDA_VERSAO="$(python3 "$PROJETO/scripts/verificar-versao.py" 2>&1)" && STATUS_VERSAO=0 || STATUS_VERSAO=$?
echo "$SAIDA_VERSAO"
case "$STATUS_VERSAO" in
  0) VERSAO_AVISO="" ;;
  1) VERSAO_AVISO="$(echo "$SAIDA_VERSAO" | grep 'Versao nova' || true)" ;;
  *) VERSAO_AVISO="Nao foi possivel conferir se ha versao nova do PJe-Calc." ;;
esac

echo ">> Extraindo indices (sem janela)..."
cd "$PROJETO"
SAIDA="$(mktemp)"
trap 'rm -f "$SAIDA"' EXIT
PJECALC_FF_HEADLESS=1 .venv/bin/python -u -m pjecalc 2>&1 | tee "$SAIDA" \
  || falhar "A extracao nao terminou."

# Quem decide o nome da pasta e o Python; aqui so lemos o que ele disse.
PASTA="$(sed -n 's/^ *Pasta : //p' "$SAIDA" | tail -1)"
echo "$MES_ATUAL" > "$MARCADOR"

CORPO="$PASTA
$(ls -1 "$PASTA" 2>/dev/null | tr '\n' ' ' || true)"
[ -n "$VERSAO_AVISO" ] && CORPO="$CORPO

$VERSAO_AVISO"
avisar "Indices TRT 8: planilhas prontas" "$CORPO"
echo "=== Fim: OK ==="
