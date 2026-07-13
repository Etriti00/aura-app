#!/usr/bin/env bash
# Aura -- macOS DMG builder
# Wraps dist/Aura.app in a drag-to-Applications disk image.
#
# The app is a native single-architecture build, so the DMG is named after the
# architecture it was built on: Apple Silicon and Intel Macs get their own
# installer. Run this on the machine that produced the .app.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VERSION="${AURA_VERSION:-2.6.0}"
APP_PATH="${1:-dist/Aura.app}"

if [ ! -d "$APP_PATH" ]; then
  echo "error: $APP_PATH not found" >&2
  exit 1
fi

case "$(uname -m)" in
  arm64)  ARCH_LABEL="AppleSilicon" ;;
  x86_64) ARCH_LABEL="Intel" ;;
  *)      echo "error: unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac

OUT="Aura-macOS-${ARCH_LABEL}.dmg"
STAGE="$(mktemp -d)"

# ditto, not cp: it preserves the bundle's code signature and extended
# attributes. A signature damaged in transit makes macOS refuse to open the app.
ditto "$APP_PATH" "$STAGE/Aura.app"
ln -s /Applications "$STAGE/Applications"
cp "$SCRIPT_DIR/FIRST_LAUNCH.txt" "$STAGE/Read Me First.txt"

hdiutil create \
  -volname "Aura $VERSION ($ARCH_LABEL)" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$OUT"

rm -rf "$STAGE"
echo "Built $OUT"
