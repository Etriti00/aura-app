#!/bin/bash
# Generate macOS .icns icon from PNG using iconutil (macOS only)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PNG_PATH="$PROJECT_ROOT/assets/icons/aura_icon.png"
ICNS_PATH="$PROJECT_ROOT/assets/icons/aura_icon.icns"
ICONSET_DIR="$PROJECT_ROOT/aura_icon.iconset"

if [ ! -f "$PNG_PATH" ]; then
    echo "Error: $PNG_PATH not found"
    exit 1
fi

echo "Generating .icns from $PNG_PATH..."
mkdir -p "$ICONSET_DIR"

for size in 16 32 64 128 256 512; do
    sips -z $size $size "$PNG_PATH" --out "$ICONSET_DIR/icon_${size}x${size}.png" 2>/dev/null
    double=$((size * 2))
    sips -z $double $double "$PNG_PATH" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" 2>/dev/null
done

iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
rm -rf "$ICONSET_DIR"

echo "Created $ICNS_PATH"
