#!/usr/bin/env bash
# Aura self-extracting installer stub. Everything below the marker line is
# a gzip tarball; this stub carves it out, unpacks it, and runs the guided
# installer inside.
set -euo pipefail

echo ""
echo "  Aura installer"
echo "  =============="
echo ""

WORK="$(mktemp -d)"
trap 'test -d "$WORK" && rm -r "$WORK"' EXIT

MARKER="__AURA_PAYLOAD__"
ARCHIVE_LINE=$(grep -an "^${MARKER}\$" "$0" | head -1 | cut -d: -f1)
ARCHIVE_LINE=$((ARCHIVE_LINE + 1))
tail -n +"$ARCHIVE_LINE" "$0" | tar -xz -C "$WORK"

bash "$WORK/install_payload.sh"
exit 0

__AURA_PAYLOAD__