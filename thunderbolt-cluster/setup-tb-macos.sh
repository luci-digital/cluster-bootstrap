#!/bin/bash
# Thunderbolt AIFAM Cluster - macOS Node Setup
# Run on Mac Mini or Intel Mac

NODE_IP=${1:-"10.0.0.10"}

echo "=== macOS Thunderbolt Cluster Setup ==="

# Find TB Bridge interface
TB_IFACE=$(networksetup -listallhardwareports | grep -A1 "Thunderbolt" | grep Device | awk '{print $2}')

if [ -z "$TB_IFACE" ]; then
    echo "No Thunderbolt Bridge interface found."
    echo "Available interfaces:"
    networksetup -listallhardwareports
    exit 1
fi

echo "Found Thunderbolt interface: $TB_IFACE"

# Configure IP
echo "Configuring IP: $NODE_IP"
sudo networksetup -setmanual "Thunderbolt Bridge" $NODE_IP 255.255.255.0

# Enable IP forwarding (if needed)
# sudo sysctl -w net.inet.ip.forwarding=1

# Test
echo "Testing connectivity..."
ping -c 2 10.0.0.1 && echo "✓ Connected to head node" || echo "✗ Head node not reachable"

echo ""
echo "=== macOS Setup Complete ==="
echo "IP: $NODE_IP"
ifconfig $TB_IFACE | grep inet
