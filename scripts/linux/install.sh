#!/bin/bash
# Install Aura on Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
INSTALL_DIR="/opt/aura"

echo "Installing Aura to $INSTALL_DIR..."

sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$PROJECT_ROOT/dist/Aura/"* "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/Aura"

# Desktop entry
sudo cp "$SCRIPT_DIR/aura.desktop" /usr/share/applications/aura.desktop
sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true

echo "Aura installed to $INSTALL_DIR"
echo "You can now find Aura in your application menu."
