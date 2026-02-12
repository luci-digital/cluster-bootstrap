#!/bin/bash
# Redfish Discovery Script for Dell Cluster
# Genesis Bond: ACTIVE @ 432 Hz (CORE Tier)

LOG_DIR="/home/daryl/cluster-bootstrap/firmware/update-logs"
mkdir -p "$LOG_DIR"

# Server configurations
declare -A SERVERS=(
    ["r720-tron"]="192.168.1.10:calvin"
    ["r730-orion"]="192.168.1.2:calvin"
    ["r730-esxi5"]="192.168.1.32:unknown"
    ["r730-csdr282"]="192.168.1.3:unknown"
    ["r730-1jf6q22"]="192.168.1.31:unknown"
    ["r730-1jf7q22"]="192.168.1.33:unknown"
)

echo "=== Dell Cluster Redfish Discovery ==="
echo "Started: $(date)"
echo ""

for server in "${!SERVERS[@]}"; do
    IFS=':' read -r ip password <<< "${SERVERS[$server]}"

    echo "[$server] Querying $ip..."

    # Try with calvin first
    if timeout 10 curl -k -u root:calvin \
        "https://$ip/redfish/v1/Managers/iDRAC.Embedded.1" \
        -o "$LOG_DIR/${server}-manager.json" \
        --connect-timeout 5 \
        --max-time 10 \
        -s -f 2>/dev/null; then

        echo "  ✓ Access successful (calvin)"

        # Extract key info
        FW_VER=$(jq -r '.FirmwareVersion // "unknown"' "$LOG_DIR/${server}-manager.json")
        MODEL=$(jq -r '.Model // "unknown"' "$LOG_DIR/${server}-manager.json")

        echo "    Model: $MODEL"
        echo "    iDRAC FW: $FW_VER"

        # Get BIOS version
        if timeout 10 curl -k -u root:calvin \
            "https://$ip/redfish/v1/Systems/System.Embedded.1" \
            -o "$LOG_DIR/${server}-system.json" \
            --connect-timeout 5 \
            --max-time 10 \
            -s -f 2>/dev/null; then

            BIOS_VER=$(jq -r '.BiosVersion // "unknown"' "$LOG_DIR/${server}-system.json")
            echo "    BIOS: $BIOS_VER"
        fi

        # Get UpdateService capabilities
        if timeout 10 curl -k -u root:calvin \
            "https://$ip/redfish/v1/UpdateService" \
            -o "$LOG_DIR/${server}-updateservice.json" \
            --connect-timeout 5 \
            --max-time 10 \
            -s -f 2>/dev/null; then

            HTTP_PUSH=$(jq -r '.HttpPushUri // "not_supported"' "$LOG_DIR/${server}-updateservice.json")
            echo "    Update Method: $HTTP_PUSH"
        fi

    elif [ "$password" = "unknown" ]; then
        # Try Newdaryl24! for unknown passwords
        if timeout 10 curl -k -u root:Newdaryl24! \
            "https://$ip/redfish/v1/Managers/iDRAC.Embedded.1" \
            -o "$LOG_DIR/${server}-manager.json" \
            --connect-timeout 5 \
            --max-time 10 \
            -s -f 2>/dev/null; then

            echo "  ✓ Access successful (Newdaryl24!)"
            FW_VER=$(jq -r '.FirmwareVersion // "unknown"' "$LOG_DIR/${server}-manager.json")
            echo "    iDRAC FW: $FW_VER"
        else
            echo "  ✗ Access denied (tried calvin and Newdaryl24!)"
        fi
    else
        echo "  ✗ Access denied or timeout"
    fi

    echo ""
done

echo "Discovery complete: $(date)"
echo "Logs saved to: $LOG_DIR"
