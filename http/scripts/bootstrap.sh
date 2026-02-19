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
