#!/usr/bin/env bash
# Aura -- macOS DMG builder
# Wraps dist/Aura.app in a drag-to-Applications disk image.
set -euo pipefail

VERSION="${AURA_VERSION:-2.6.0}"
APP_PATH="${1:-dist/Aura.app}"
OUT="Aura-macOS-Installer.dmg"
STAGE="$(mktemp -d)"

if [ ! -d "$APP_PATH" ]; then
  echo "error: $APP_PATH not found" >&2
  exit 1
fi

cp -R "$APP_PATH" "$STAGE/Aura.app"
ln -s /Applications "$STAGE/Applications"

hdiutil create \
  -volname "Aura $VERSION" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$OUT"

rm -rf "$STAGE"
echo "Built $OUT"