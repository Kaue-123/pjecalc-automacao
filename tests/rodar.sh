#!/usr/bin/env bash
# Roda a suite inteira. Nada aqui sobe o PJe-Calc, abre navegador ou acessa a
# rede: tudo que toca o mundo esta substituido por duble.
#
# A extracao em si (Selenium contra o PJe-Calc) nao da para testar assim — essa
# so se verifica rodando de verdade: ./scripts/rodada-mensal.sh --forcar
set -uo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || PY=python3
FALHOU=0

titulo() { echo; echo "═══ $1 ═══"; }

titulo "datas, indices e nomes de arquivo"
"$PY" "$RAIZ/tests/test_datas.py" 2>&1 | grep -E "^(OK|FAILED|Ran)" || FALHOU=1

titulo "tabela extraida"
"$PY" "$RAIZ/tests/test_tabela.py" 2>&1 | grep -E "^(OK|FAILED|Ran)" || FALHOU=1

titulo "saida no terminal"
"$PY" "$RAIZ/tests/test_console.py" 2>&1 | grep -E "^(OK|FAILED|Ran)" || FALHOU=1

titulo "verificacao de versao"
"$PY" "$RAIZ/tests/test_verificar_versao.py" 2>&1 | grep -E "^(OK|FAILED|Ran)" || FALHOU=1

titulo "agenda do timer"
"$PY" "$RAIZ/tests/test_timer.py" 2>&1 | grep -E "^(OK|FAILED|Ran)" || FALHOU=1

titulo "lancador"
"$RAIZ/tests/test_lancador.sh" || FALHOU=1

titulo "rodada mensal"
"$RAIZ/tests/test_rodada_mensal.sh" || FALHOU=1

echo
if [ "$FALHOU" -eq 0 ]; then echo "✓ suite inteira passou"; else echo "✗ ha falhas acima"; fi
exit "$FALHOU"
