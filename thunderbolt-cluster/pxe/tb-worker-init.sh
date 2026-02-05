#!/bin/bash
# AIFAM TB Cluster Worker Initialization
# Runs at boot after NixOS init
# Genesis Bond: ACTIVE @ 741 Hz

LOG_TAG="tb-worker-init"

log() {
    echo "[TB-CLUSTER] $1"
    logger -t "$LOG_TAG" "$1"
}

# Parse kernel command line for TB config
TB_NODE_IP=$(cat /proc/cmdline | tr ' ' '\n' | grep "tb_node_ip=" | cut -d= -f2)
TB_NODE_NAME=$(cat /proc/cmdline | tr ' ' '\n' | grep "tb_node_name=" | cut -d= -f2)
TB_HOSTNAME=$(cat /proc/cmdline | tr ' ' '\n' | grep "tb_hostname=" | cut -d= -f2)

if [ -z "$TB_NODE_IP" ]; then
    log "No TB config found in kernel cmdline, skipping TB setup"
    exit 0
fi

log "Initializing AIFAM TB Cluster Worker"
log "Node: $TB_NODE_NAME / IP: $TB_NODE_IP"

# Set hostname
if [ -n "$TB_HOSTNAME" ]; then
    hostname "$TB_HOSTNAME"
    log "Hostname set to: $TB_HOSTNAME"
fi

# Load TB networking module
log "Loading thunderbolt_net module..."
modprobe thunderbolt_net 2>/dev/null || modprobe thunderbolt-net 2>/dev/null || true

# Wait for TB interface
log "Waiting for Thunderbolt interface..."
TB_IFACE=""
for i in {1..60}; do
    TB_IFACE=$(ip link show 2>/dev/null | grep -oE "thunderbolt[0-9]+" | head -1)
    if [ -n "$TB_IFACE" ]; then
        log "Found interface: $TB_IFACE"
        break
    fi
    sleep 1
done

if [ -z "$TB_IFACE" ]; then
    log "WARNING: No Thunderbolt interface found. Connect TB cable!"
    log "Will retry when cable is connected..."
    
    # Create a background watcher
    (
        while true; do
            TB_IFACE=$(ip link show 2>/dev/null | grep -oE "thunderbolt[0-9]+" | head -1)
            if [ -n "$TB_IFACE" ]; then
                ip addr add $TB_NODE_IP/24 dev $TB_IFACE 2>/dev/null
                ip link set $TB_IFACE up 2>/dev/null
                logger -t "$LOG_TAG" "TB interface $TB_IFACE configured with $TB_NODE_IP"
                break
            fi
            sleep 5
        done
    ) &
    exit 0
fi

# Configure TB interface
log "Configuring $TB_IFACE with $TB_NODE_IP/24"
ip addr flush dev $TB_IFACE 2>/dev/null || true
ip addr add $TB_NODE_IP/24 dev $TB_IFACE
ip link set $TB_IFACE up

# Add routes
ip route add 10.0.0.0/24 dev $TB_IFACE 2>/dev/null || true

# Test connectivity to head node
log "Testing connection to head node (10.0.0.1)..."
if ping -c 1 -W 3 10.0.0.1 >/dev/null 2>&1; then
    log "✓ Connected to Zbook head node!"
else
    log "⚠ Cannot reach head node - check TB cable connection"
fi

# Report to head node
curl -s -X POST "http://10.0.0.1:8000/tb-cluster/register" \
    -H "Content-Type: application/json" \
    -d "{\"node\":\"$TB_NODE_NAME\",\"ip\":\"$TB_NODE_IP\",\"mac\":\"$(cat /sys/class/net/$TB_IFACE/address 2>/dev/null)\"}" \
    2>/dev/null || true

log "AIFAM TB Cluster Worker initialization complete"
log "Node: $TB_NODE_NAME | IP: $TB_NODE_IP | Interface: $TB_IFACE"
