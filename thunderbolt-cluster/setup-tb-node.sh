#!/bin/bash
# Thunderbolt AIFAM Cluster - Node Setup Script
# Usage: ./setup-tb-node.sh <node-ip> [head|worker]

set -e

NODE_IP=${1:-"10.0.0.1"}
NODE_ROLE=${2:-"worker"}
TB_IFACE=""

echo "=== Thunderbolt AIFAM Cluster Node Setup ==="
echo "Node IP: $NODE_IP"
echo "Role: $NODE_ROLE"

# Load TB networking module
echo "[1/6] Loading thunderbolt_net module..."
sudo modprobe thunderbolt_net

# Wait for TB interface
echo "[2/6] Waiting for Thunderbolt interface..."
for i in {1..30}; do
    TB_IFACE=$(ip link show | grep -E "thunderbolt|enp.*tb" | awk -F: '{print $2}' | tr -d ' ' | head -1)
    if [ -n "$TB_IFACE" ]; then
        echo "Found: $TB_IFACE"
        break
    fi
    sleep 1
done

if [ -z "$TB_IFACE" ]; then
    echo "No Thunderbolt interface found. Connect a TB device first."
    echo "Checking connected TB devices:"
    boltctl list
    exit 1
fi

# Configure IP
echo "[3/6] Configuring IP address..."
sudo ip addr flush dev $TB_IFACE 2>/dev/null || true
sudo ip addr add $NODE_IP/24 dev $TB_IFACE
sudo ip link set $TB_IFACE up

# Enable forwarding for head node
if [ "$NODE_ROLE" == "head" ]; then
    echo "[4/6] Configuring as HEAD node (routing enabled)..."
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo sysctl -w net.ipv6.conf.all.forwarding=1
    
    # If second TB interface exists, create bridge
    TB_IFACE2=$(ip link show | grep -E "thunderbolt|enp.*tb" | awk -F: '{print $2}' | tr -d ' ' | tail -1)
    if [ "$TB_IFACE" != "$TB_IFACE2" ] && [ -n "$TB_IFACE2" ]; then
        echo "Creating bridge for multiple TB interfaces..."
        sudo ip link add name tb-bridge type bridge 2>/dev/null || true
        sudo ip link set $TB_IFACE master tb-bridge
        sudo ip link set $TB_IFACE2 master tb-bridge
        sudo ip addr add $NODE_IP/24 dev tb-bridge
        sudo ip link set tb-bridge up
    fi
else
    echo "[4/6] Configuring as WORKER node..."
fi

# Add route to cluster network
echo "[5/6] Adding routes..."
# Route to other nodes via head node (if worker)
if [ "$NODE_ROLE" == "worker" ]; then
    sudo ip route add 10.0.0.0/24 dev $TB_IFACE 2>/dev/null || true
fi

# Test connectivity
echo "[6/6] Testing connectivity..."
ping -c 1 -W 2 10.0.0.1 && echo "✓ Head node reachable" || echo "✗ Head node not reachable (expected if first node)"

echo ""
echo "=== Setup Complete ==="
echo "Interface: $TB_IFACE"
echo "IP: $NODE_IP/24"
ip addr show $TB_IFACE | grep inet
