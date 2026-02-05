#!/bin/bash
# Build TB Cluster initrd overlay (CPIO archive)
# This overlay contains TB worker setup scripts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/tmp/tb-initrd-build"
OUTPUT="/srv/tftp/tb-cluster/tb-setup.cpio"

echo "Building AIFAM TB Cluster initrd overlay..."

# Clean and create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"/{etc/systemd/system,usr/local/bin}

# Copy init script
cp "$SCRIPT_DIR/tb-worker-init.sh" "$BUILD_DIR/usr/local/bin/"
chmod +x "$BUILD_DIR/usr/local/bin/tb-worker-init.sh"

# Create systemd service for TB init
cat > "$BUILD_DIR/etc/systemd/system/tb-worker.service" << 'SVCEOF'
[Unit]
Description=AIFAM Thunderbolt Cluster Worker Setup
After=network.target thunderbolt.service
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/tb-worker-init.sh

[Install]
WantedBy=multi-user.target
SVCEOF

# Create symlink for auto-start
mkdir -p "$BUILD_DIR/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/tb-worker.service \
    "$BUILD_DIR/etc/systemd/system/multi-user.target.wants/tb-worker.service"

# Create the CPIO archive
sudo mkdir -p "$(dirname "$OUTPUT")"
cd "$BUILD_DIR"
find . | cpio -o -H newc | gzip > "$OUTPUT"

echo "✓ Built: $OUTPUT"
ls -lh "$OUTPUT"

# Cleanup
rm -rf "$BUILD_DIR"
