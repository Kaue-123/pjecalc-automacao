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

echo
echo "Pronto. Proxima rodada:"
systemctl --user list-timers pjecalc-indices.timer --no-pager
