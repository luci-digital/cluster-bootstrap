#!/bin/bash
# Lenovo X1 Carbon Gen 10 - AIFAM TB Worker Setup
# Run this on the Lenovo laptop

NODE_IP="10.0.0.3"
HOSTNAME="lenovo.tb.lucidigital.net"

echo "=== Lenovo X1 AIFAM Worker Setup ==="
echo "Node IP: $NODE_IP"

# Set hostname
sudo hostnamectl set-hostname $HOSTNAME

# Load TB networking
sudo modprobe thunderbolt_net

# Wait for interface
echo "Waiting for Thunderbolt interface..."
for i in {1..30}; do
    TB_IFACE=$(ip link show | grep -oE "thunderbolt[0-9]+" | head -1)
    [ -n "$TB_IFACE" ] && break
    sleep 1
done

if [ -z "$TB_IFACE" ]; then
    echo "ERROR: No TB interface. Connect TB cable first!"
    exit 1
fi

echo "Found: $TB_IFACE"

# Configure IP
sudo ip addr flush dev $TB_IFACE
sudo ip addr add $NODE_IP/24 dev $TB_IFACE
sudo ip link set $TB_IFACE up

# Add route
sudo ip route add 10.0.0.0/24 dev $TB_IFACE

# Test connectivity
echo "Testing connections..."
ping -c 1 10.0.0.1 && echo "✓ Zbook (head)" || echo "✗ Zbook"
ping -c 1 10.0.0.2 && echo "✓ Dell" || echo "✗ Dell"

echo ""
echo "=== Setup Complete ==="
ip addr show $TB_IFACE | grep inet
