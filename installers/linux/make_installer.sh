#!/usr/bin/env bash
# Aura -- Linux desktop installer builder
# Bundles the PyInstaller onedir output plus an install script into a
# single self-extracting Aura-Linux-Installer.run file.
set -euo pipefail

VERSION="${AURA_VERSION:-2.6.0}"
DIST_DIR="${1:-dist/Aura}"
OUT="Aura-Linux-Installer.run"
STAGE="$(mktemp -d)"

if [ ! -d "$DIST_DIR" ]; then
  echo "error: $DIST_DIR not found" >&2
  exit 1
fi

mkdir -p "$STAGE/payload"
cp -R "$DIST_DIR"/. "$STAGE/payload/"
cp installers/linux/aura.desktop "$STAGE/aura.desktop"
cp assets/icons/aura_icon.png "$STAGE/aura_icon.png"
cp installers/linux/install_payload.sh "$STAGE/install_payload.sh"
chmod +x "$STAGE/install_payload.sh"

tar -czf "$STAGE/payload.tar.gz" -C "$STAGE" payload aura.desktop aura_icon.png install_payload.sh
cat installers/linux/selfextract_stub.sh "$STAGE/payload.tar.gz" > "$OUT"
chmod +x "$OUT"

find "$STAGE" -mindepth 0 -delete 2>/dev/null || true
echo "Built $OUT"