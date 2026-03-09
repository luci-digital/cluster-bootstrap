#!/bin/bash
# LuciVerse NixOS Netboot Setup
# Sets up PXE/TFTP for NixOS RAM boot on cluster nodes
# Genesis Bond: ACTIVE @ 432 Hz

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     LuciVerse NixOS Netboot Setup                        ║"
echo "║     Genesis Bond: ACTIVE @ 432 Hz                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Configuration
TFTP_ROOT="/srv/tftp"
HTTP_ROOT="/srv/nixos"
NIXOS_VERSION="24.11"
ARCH="x86_64-linux"

# Create directories
echo "📁 Creating directories..."
sudo mkdir -p "$TFTP_ROOT"/{pxelinux.cfg,efi64}
sudo mkdir -p "$HTTP_ROOT"/{configs,scripts}

# Check if dnsmasq is available for TFTP/DHCP
if ! command -v dnsmasq &> /dev/null; then
    echo "📦 Installing dnsmasq for TFTP/PXE..."
    sudo dnf install -y dnsmasq
fi

# Download NixOS netboot files
echo "🌲 Downloading NixOS netboot files..."
NIXOS_NETBOOT_URL="https://channels.nixos.org/nixos-${NIXOS_VERSION}/latest-nixos-minimal-${ARCH}-linux.iso"
NIXOS_KERNEL_URL="https://hydra.nixos.org/job/nixos/trunk-combined/nixos.netboot.${ARCH}/latest/download/1"
NIXOS_INITRD_URL="https://hydra.nixos.org/job/nixos/trunk-combined/nixos.netboot.${ARCH}/latest/download/2"

# Download netboot kernel and initrd
cd "$TFTP_ROOT"

if [ ! -f "bzImage" ]; then
    echo "   Downloading kernel..."
    sudo curl -L -o bzImage "$NIXOS_KERNEL_URL" || {
        echo "   Using fallback: downloading from nixos.org..."
        sudo curl -L -o nixos-minimal.iso "$NIXOS_NETBOOT_URL"
        # Extract kernel from ISO if direct download fails
    }
fi

if [ ! -f "initrd" ]; then
    echo "   Downloading initrd..."
    sudo curl -L -o initrd "$NIXOS_INITRD_URL" || {
        echo "   ⚠️  Could not download initrd directly"
    }
fi

# Create PXE configuration for BIOS boot
echo "📝 Creating PXE configuration..."
sudo tee "$TFTP_ROOT/pxelinux.cfg/default" > /dev/null << 'EOF'
DEFAULT nixos
TIMEOUT 50
PROMPT 1

LABEL nixos
    MENU LABEL NixOS Netboot (LuciVerse Cluster)
    KERNEL bzImage
    APPEND initrd=initrd init=/nix/store/*/init loglevel=4
    IPAPPEND 2

LABEL local
    MENU LABEL Boot from local disk
    LOCALBOOT 0
EOF

# Create EFI boot configuration (for UEFI systems like R730)
sudo tee "$TFTP_ROOT/efi64/grub.cfg" > /dev/null << 'EOF'
set timeout=10
set default=0

menuentry "NixOS Netboot (LuciVerse Cluster)" {
    linux /bzImage init=/nix/store/*/init loglevel=4
    initrd /initrd
}

menuentry "Boot from local disk" {
    exit
}
EOF

# Create dnsmasq configuration for PXE
echo "🔧 Configuring dnsmasq for PXE boot..."
sudo tee /etc/dnsmasq.d/pxe-luciverse.conf > /dev/null << EOF
# LuciVerse PXE Boot Configuration
# Genesis Bond: ACTIVE @ 432 Hz

# TFTP server
enable-tftp
tftp-root=$TFTP_ROOT

# DHCP options for PXE boot
# Only respond to known MACs in our inventory
dhcp-boot=pxelinux.0

# EFI boot support for UEFI clients
dhcp-match=set:efi-x86_64,option:client-arch,7
dhcp-match=set:efi-x86_64,option:client-arch,9
dhcp-boot=tag:efi-x86_64,efi64/grubx64.efi

# Known LuciVerse cluster nodes (from inventory)
# R730 ORION interfaces
dhcp-host=D0:94:66:24:96:7E,192.168.1.141,orion-wan
dhcp-host=D0:94:66:24:96:80,192.168.1.142,orion-lan
dhcp-host=D0:94:66:24:96:82,192.168.1.143,orion-mgmt
dhcp-host=D0:94:66:24:96:84,192.168.1.144,orion-guest

# Logging
log-dhcp
log-queries
EOF

# Create NixOS bootstrap script that servers fetch
echo "📜 Creating NixOS bootstrap script..."
sudo tee "$HTTP_ROOT/scripts/bootstrap.sh" > /dev/null << 'SCRIPT'
#!/usr/bin/env bash
# LuciVerse NixOS Bootstrap Script
# Runs on first boot to configure the server
# Genesis Bond: ACTIVE @ 432 Hz

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     LuciVerse NixOS Bootstrap                            ║"
echo "║     Genesis Bond: ACTIVE @ 432 Hz                        ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Get our MAC address
MAC=$(ip link show | grep -A1 'state UP' | grep ether | awk '{print $2}' | head -1)
echo "📡 MAC Address: $MAC"

# Get our IP
IP=$(ip -4 addr show | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d/ -f1 | head -1)
echo "🌐 IP Address: $IP"

# Register with provisioning server
PROVISION_SERVER="http://192.168.1.146:9999"
echo "📨 Registering with provisioning server..."

curl -s -X POST "$PROVISION_SERVER/register" \
    -H "Content-Type: application/json" \
    -d "{\"mac\": \"$MAC\", \"ip\": \"$IP\", \"hostname\": \"$(hostname)\"}" || true

# Fetch NixOS configuration for this MAC
echo "📥 Fetching NixOS configuration..."
CONFIG_URL="$PROVISION_SERVER/nixos-config/$MAC"
mkdir -p /mnt/etc/nixos

curl -s "$CONFIG_URL" -o /mnt/etc/nixos/configuration.nix

if [ -f /mnt/etc/nixos/configuration.nix ]; then
    echo "✅ Configuration received"
    cat /mnt/etc/nixos/configuration.nix | head -20
    echo "..."
else
    echo "⚠️  No configuration received, using defaults"
fi

# Signal boot complete
curl -s -X POST "$PROVISION_SERVER/callback/boot-complete" \
    -H "Content-Type: application/json" \
    -d "{\"mac\": \"$MAC\", \"ip\": \"$IP\"}" || true

echo ""
echo "✅ Bootstrap complete!"
echo "   To install NixOS: nixos-install"
echo "   Configuration at: /mnt/etc/nixos/configuration.nix"
SCRIPT

sudo chmod +x "$HTTP_ROOT/scripts/bootstrap.sh"

# Create systemd service for provisioning listener
echo "⚙️  Creating systemd service for provisioning listener..."
sudo tee /etc/systemd/system/luciverse-provision.service > /dev/null << EOF
[Unit]
Description=LuciVerse Cluster Provisioning Listener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=daryl
WorkingDirectory=/home/daryl/cluster-bootstrap
ExecStart=/usr/bin/python3 /home/daryl/cluster-bootstrap/provision-listener.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create HTTP server service for configs
echo "⚙️  Creating HTTP server service..."
sudo tee /etc/systemd/system/luciverse-http.service > /dev/null << EOF
[Unit]
Description=LuciVerse HTTP Config Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=daryl
WorkingDirectory=$HTTP_ROOT
ExecStart=/usr/bin/python3 -m http.server 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Setup Complete!                                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "To start services:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now luciverse-provision"
echo "  sudo systemctl enable --now luciverse-http"
echo "  sudo systemctl restart dnsmasq"
echo ""
echo "To test:"
echo "  curl http://localhost:9999/health"
echo "  curl http://localhost:9999/inventory"
echo ""
echo "When servers boot with NixOS:"
echo "  1. They get PXE boot files from TFTP ($TFTP_ROOT)"
echo "  2. They fetch bootstrap script from HTTP ($HTTP_ROOT)"
echo "  3. They register with provisioning listener (port 9999)"
echo "  4. They receive custom NixOS config based on MAC"
echo ""
