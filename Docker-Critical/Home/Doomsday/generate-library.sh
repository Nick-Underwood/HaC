#!/usr/bin/env bash
# Helper to (re)generate library.xml for Kiwix using the official kiwix-tools container.
# Run this on the TrueNAS/host where /mnt/Apps/kiwix/zim is accessible.

DATA_DIR="/mnt/Apps/kiwix/zim"
TOOLS_IMAGE="ghcr.io/kiwix/kiwix-tools:latest"

if [ "$EUID" -ne 0 ]; then
  echo "Note: run as root or a user with access to /mnt/Apps/kiwix/zim to ensure file permissions are correct."
fi

if [ ! -d "$DATA_DIR" ]; then
  echo "Data dir $DATA_DIR does not exist. Create it and put .zim files inside."
  exit 1
fi

echo "Inspecting kiwix-tools help to determine available subcommands..."
docker run --rm -v "$DATA_DIR":/data "$TOOLS_IMAGE" --help || true

echo
echo "To generate or update the library you can run (one of these may work depending on kiwix-tools version):"

cat <<'EOF'
# Variant A (common): add all ZIMs to a new library.xml
docker run --rm -v /mnt/Apps/kiwix/zim:/data ghcr.io/kiwix/kiwix-tools kiwix-manage /data/library.xml add /data/*.zim

# Variant B (alternate syntax some versions use):
docker run --rm -v /mnt/Apps/kiwix/zim:/data ghcr.io/kiwix/kiwix-tools kiwix-manage add /data/library.xml /data/*.zim

# If you just want to inspect a ZIM or test the tools first:
docker run --rm -v /mnt/Apps/kiwix/zim:/data ghcr.io/kiwix/kiwix-tools kiwix-manage --help
EOF

exit 0
