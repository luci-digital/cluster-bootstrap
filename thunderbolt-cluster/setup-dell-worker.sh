#!/bin/bash
# Dell Latitude 7450 - AIFAM TB Worker Setup
# Run this on the Dell laptop

NODE_IP="10.0.0.2"
HOSTNAME="dell.tb.lucidigital.net"

echo "=== Dell 7450 AIFAM Worker Setup ==="
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

# Add route to other nodes
sudo ip route add 10.0.0.0/24 dev $TB_IFACE

# Test head node
echo "Testing connection to head node..."
ping -c 2 10.0.0.1 && echo "✓ Connected to Zbook!" || echo "✗ Cannot reach head node"

echo ""
echo "=== Setup Complete ==="
ip addr show $TB_IFACE | grep inet
