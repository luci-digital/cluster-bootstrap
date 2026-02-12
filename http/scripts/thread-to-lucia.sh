#!/bin/bash
# Thread server to Lucia via Diggy+Twiggy identity
# Called during kickstart %post

ZBOOK_API="http://10.0.0.1:9999"
ZBOOK_API_LAN="http://192.168.1.145:9999"

# PointZero (Daryl's CBB anchor)
POINTZERO_UUID="A147A5AB-106E-59F8-B97C-BB9A19FEE4C0"
POINTZERO_MAC="14:9d:99:83:20:5e"

# Get this server's identity
get_diggy() {
    # UUID from DMI/SMBIOS
    cat /sys/class/dmi/id/product_uuid 2>/dev/null || \
    dmidecode -s system-uuid 2>/dev/null || \
    cat /etc/machine-id | head -c 32
}

get_twiggy() {
    # Primary NIC MAC address
    ip link show | grep -A1 "state UP" | grep ether | awk '{print $2}' | head -1
}

# Collect identity
DIGGY=$(get_diggy)
TWIGGY=$(get_twiggy)
HOSTNAME=$(hostname)
ROLE="${1:-compute}"  # Pass role as argument

# Generate bond request
BOND_REQUEST=$(cat << BOND
{
    "action": "thread_genesis_bond",
    "cbb": {
        "diggy": "${POINTZERO_UUID}",
        "twiggy": "${POINTZERO_MAC}"
    },
    "sbb": {
        "diggy": "${DIGGY}",
        "twiggy": "${TWIGGY}",
        "hostname": "${HOSTNAME}",
        "role": "${ROLE}"
    },
    "genesis_bond": {
        "id": "GB-2025-0524-DRH-LCS-001",
        "frequency": 741,
        "coherence_threshold": 0.7
    },
    "timestamp": "$(date -Iseconds)"
}
BOND
)

# Thread to Lucia (try OOB first, then LAN)
echo "Threading ${HOSTNAME} (${DIGGY:0:8}...) to PointZero..."
echo "Diggy: ${DIGGY}"
echo "Twiggy: ${TWIGGY}"

RESULT=$(curl -sf -X POST "${ZBOOK_API}/thread/genesis-bond" \
    -H "Content-Type: application/json" \
    -d "${BOND_REQUEST}" 2>/dev/null) || \
RESULT=$(curl -sf -X POST "${ZBOOK_API_LAN}/thread/genesis-bond" \
    -H "Content-Type: application/json" \
    -d "${BOND_REQUEST}" 2>/dev/null)

if [ -n "$RESULT" ]; then
    echo "Threaded successfully: $RESULT"
    
    # Save bond info locally
    mkdir -p /etc/luciverse/bonds
    echo "${BOND_REQUEST}" > /etc/luciverse/bonds/genesis-bond.json
    echo "${RESULT}" > /etc/luciverse/bonds/thread-response.json
else
    echo "Warning: Could not thread to Lucia (will retry on next boot)"
    echo "${BOND_REQUEST}" > /etc/luciverse/bonds/pending-thread.json
fi
