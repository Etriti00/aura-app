#!/usr/bin/env bash
# Aura headless installer for Raspberry Pi and VPS servers.
# Downloads the latest CLI build for this architecture, unpacks it to
# ~/.local/share/aura-cli, and symlinks aura onto your PATH.
set -euo pipefail

REPO="Etriti00/aura-app"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ASSET="Aura-Server-Linux-x64.tar.gz" ;;
  aarch64|arm64) ASSET="Aura-RaspberryPi-arm64.tar.gz" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

URL="https://github.com/$REPO/releases/latest/download/$ASSET"
PREFIX="$HOME/.local/share/aura-cli"
BIN="$HOME/.local/bin/aura"

echo "Installing Aura CLI ($ASSET) ..."
mkdir -p "$PREFIX" "$(dirname "$BIN")"
TMP="$(mktemp -d)"

curl -fsSL "$URL" -o "$TMP/aura.tar.gz"
tar -xzf "$TMP/aura.tar.gz" -C "$TMP"
find "$PREFIX" -mindepth 1 -delete 2>/dev/null || true
cp -R "$TMP/aura-cli/." "$PREFIX/"
ln -sf "$PREFIX/aura-cli" "$BIN"
find "$TMP" -mindepth 0 -delete 2>/dev/null || true

echo ""
echo "Installed. Ensure ~/.local/bin is on your PATH, then run:"
echo "  aura --help"
echo "  aura repl"