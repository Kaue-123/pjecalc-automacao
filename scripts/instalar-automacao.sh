#!/usr/bin/env bash
# Instala as unidades de usuario da rodada mensal, com o caminho real do
# repositorio no lugar do placeholder __PROJETO__.
set -euo pipefail

SCRIPTS="$(dirname "$(readlink -f "$0")")"
PROJETO="$(cd "$SCRIPTS/.." && pwd)"
DESTINO="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

mkdir -p "$DESTINO"
sed "s|__PROJETO__|$PROJETO|" "$SCRIPTS/pjecalc-indices.service" > "$DESTINO/pjecalc-indices.service"
cp "$SCRIPTS/pjecalc-indices.timer" "$DESTINO/"
cp "$SCRIPTS/pjecalc.service" "$DESTINO/"

systemctl --user daemon-reload
systemctl --user enable --now pjecalc.service
systemctl --user enable --now pjecalc-indices.timer

# Sem linger, as unidades --user morrem junto com a ultima sessao do usuario.
# Numa estacao de trabalho isso nao aparece, porque a sessao grafica fica aberta;
# num servidor, basta sair do SSH para o timer deixar de existir — sem erro,
# sem log, sem rodada no dia 6.
if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
  echo
  echo ">> Habilitando linger (unidades --user sobrevivem ao logout)..."
  if loginctl enable-linger "$USER" 2>/dev/null; then
    echo "   ok"
  else
    echo "   NAO FOI POSSIVEL. Rode como administrador:"
    echo "     sudo loginctl enable-linger $USER"
    echo "   Sem isso, num servidor o timer para de existir quando voce sair da sessao."
  fi
fi

echo
echo "Linger: $(loginctl show-user "$USER" -p Linger --value 2>/dev/null)"
echo "Proxima rodada:"
systemctl --user list-timers pjecalc-indices.timer --no-pager
