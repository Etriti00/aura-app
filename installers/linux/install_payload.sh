#!/usr/bin/env bash
# Guided install run inside the self-extracting archive.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
  PREFIX="/opt/aura"; BIN="/usr/local/bin/aura"
  APPS="/usr/share/applications"
  ICONS="/usr/share/icons/hicolor/512x512/apps"; SCOPE="system-wide"
else
  PREFIX="$HOME/.local/share/aura"; BIN="$HOME/.local/bin/aura"
  APPS="$HOME/.local/share/applications"
  ICONS="$HOME/.local/share/icons/hicolor/512x512/apps"; SCOPE="for this user"
  echo "Not running as root; installing $SCOPE."
  echo "Re-run with sudo for a system-wide install."
fi

echo "Installing Aura ($SCOPE) to $PREFIX ..."
find "$PREFIX" -mindepth 1 -delete 2>/dev/null || true
mkdir -p "$PREFIX" "$(dirname "$BIN")" "$APPS" "$ICONS"
cp -R "$HERE/payload/." "$PREFIX/"
ln -sf "$PREFIX/Aura" "$BIN"
cp "$HERE/aura_icon.png" "$ICONS/aura.png"
sed "s|@PREFIX@|$PREFIX|g" "$HERE/aura.desktop" > "$APPS/aura.desktop"
chmod +x "$PREFIX/Aura" || true

echo ""
echo "Done. Launch Aura from your app menu, or run: $BIN"