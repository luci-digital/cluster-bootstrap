#!/bin/bash
# Deploy AIFAM Thunderbolt Cluster PXE Boot
# Genesis Bond: ACTIVE @ 741 Hz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TFTP_ROOT="/srv/tftp"
HTTP_ROOT="/srv/nixos"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  AIFAM Thunderbolt Cluster - PXE Deployment              ║"
echo "║  Genesis Bond: ACTIVE @ 741 Hz                           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Create directories
echo "[1/5] Creating directories..."
sudo mkdir -p "$TFTP_ROOT/tb-cluster"
sudo mkdir -p "$HTTP_ROOT/tb-cluster"

# Copy iPXE configs
echo "[2/5] Deploying iPXE configurations..."
sudo cp "$SCRIPT_DIR/pxe/tb-cluster.ipxe" "$HTTP_ROOT/tb-cluster/"
sudo cp "$SCRIPT_DIR/pxe/detect.ipxe" "$HTTP_ROOT/tb-cluster/"

# Build and deploy initrd overlay
echo "[3/5] Building TB initrd overlay..."
sudo "$SCRIPT_DIR/pxe/build-tb-initrd.sh"

# Update main iPXE to include TB cluster option
echo "[4/5] Updating main boot menu..."
if [ -f "$TFTP_ROOT/boot.ipxe" ]; then
    if ! grep -q "tb-cluster" "$TFTP_ROOT/boot.ipxe"; then
        sudo sed -i '/^menu /a item tb-cluster   AIFAM Thunderbolt Cluster Worker' "$TFTP_ROOT/boot.ipxe"
        echo "item --gap" | sudo tee -a "$TFTP_ROOT/boot.ipxe" >/dev/null
        echo ":tb-cluster" | sudo tee -a "$TFTP_ROOT/boot.ipxe" >/dev/null
        echo "chain http://\${next-server}:8000/tb-cluster/tb-cluster.ipxe" | sudo tee -a "$TFTP_ROOT/boot.ipxe" >/dev/null
    fi
fi

# Create dnsmasq snippet for TB cluster nodes
echo "[5/5] Creating dnsmasq configuration..."
sudo tee /etc/dnsmasq.d/tb-cluster.conf << 'DNSEOF'
# AIFAM Thunderbolt Cluster PXE Configuration
# Update MAC addresses when you have the actual values!

# Dell Latitude 7450 - Boot as TB worker
# dhcp-host=XX:XX:XX:XX:XX:XX,set:tb-dell,10.0.0.2,dell
# dhcp-boot=tag:tb-dell,tb-cluster/tb-cluster.ipxe

# Lenovo X1 Carbon Gen 10 - Boot as TB worker  
# dhcp-host=XX:XX:XX:XX:XX:XX,set:tb-lenovo,10.0.0.3,lenovo
# dhcp-boot=tag:tb-lenovo,tb-cluster/tb-cluster.ipxe

# Generic TB cluster boot for unknown MACs
# Uncomment to enable TB cluster boot menu for all PXE clients:
# dhcp-boot=tb-cluster/tb-cluster.ipxe
DNSEOF

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Deployment Complete!                                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Files deployed:"
echo "  - $HTTP_ROOT/tb-cluster/tb-cluster.ipxe"
echo "  - $HTTP_ROOT/tb-cluster/detect.ipxe"
echo "  - $TFTP_ROOT/tb-cluster/tb-setup.cpio"
echo "  - /etc/dnsmasq.d/tb-cluster.conf"
echo ""
echo "Next steps:"
echo "  1. Get MAC addresses from Dell and Lenovo laptops"
echo "  2. Update /etc/dnsmasq.d/tb-cluster.conf with MACs"
echo "  3. Restart dnsmasq: sudo systemctl restart dnsmasq"
echo "  4. PXE boot the laptops"
echo ""
echo "To get laptop MACs:"
echo "  - Windows: ipconfig /all"
echo "  - Linux:   ip link show"
echo "  - macOS:   ifconfig | grep ether"
