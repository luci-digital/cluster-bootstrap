#!/bin/bash
# Redfish API Discovery Script for 6 Dell Servers
# Phase 1: Connectivity and Firmware Inventory

declare -A SERVERS
SERVERS=(
    ["R720_tron"]="192.168.1.10"
    ["R730_ORION"]="192.168.1.2"
    ["R730_ESXi5"]="192.168.1.32"
    ["R730_CSDR282"]="192.168.1.3"
    ["R730_1JF6Q22"]="192.168.1.31"
    ["R730_1JF7Q22"]="192.168.1.33"
)

CREDS=("root:calvin" "root:Newdaryl24!")

echo "=== REDFISH API DISCOVERY - $(date) ==="
echo ""

for server_name in "${!SERVERS[@]}"; do
    ip="${SERVERS[$server_name]}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $server_name ($ip)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Test connectivity first
    if ! ping -c 1 -W 2 "$ip" &>/dev/null; then
        echo "❌ UNREACHABLE - Cannot ping $ip"
        echo ""
        continue
    fi
    
    echo "✓ Network reachable"
    
    # Try each credential
    working_cred=""
    for cred in "${CREDS[@]}"; do
        echo -n "Testing credentials: ${cred%%:*}:*** ... "
        
        response=$(curl -sk -u "$cred" -w "\n%{http_code}" \
            "https://$ip/redfish/v1/Managers/iDRAC.Embedded.1" 2>/dev/null)
        
        http_code=$(echo "$response" | tail -1)
        
        if [ "$http_code" = "200" ]; then
            echo "✓ SUCCESS"
            working_cred="$cred"
            break
        else
            echo "✗ Failed (HTTP $http_code)"
        fi
    done
    
    if [ -z "$working_cred" ]; then
        echo "❌ NO VALID CREDENTIALS FOUND"
        echo ""
        continue
    fi
    
    echo ""
    echo "📊 Gathering firmware inventory..."
    
    # Get iDRAC Manager info
    manager_info=$(curl -sk -u "$working_cred" \
        "https://$ip/redfish/v1/Managers/iDRAC.Embedded.1" 2>/dev/null)
    
    # Get System info for BIOS
    system_info=$(curl -sk -u "$working_cred" \
        "https://$ip/redfish/v1/Systems/System.Embedded.1" 2>/dev/null)
    
    # Extract versions using grep/sed (more portable than jq)
    idrac_version=$(echo "$manager_info" | grep -o '"FirmwareVersion":"[^"]*"' | cut -d'"' -f4)
    model=$(echo "$manager_info" | grep -o '"Model":"[^"]*"' | cut -d'"' -f4)
    bios_version=$(echo "$system_info" | grep -o '"BiosVersion":"[^"]*"' | cut -d'"' -f4)
    power_state=$(echo "$system_info" | grep -o '"PowerState":"[^"]*"' | cut -d'"' -f4)
    
    echo "  Model: $model"
    echo "  iDRAC Firmware: ${idrac_version:-UNKNOWN}"
    echo "  BIOS Version: ${bios_version:-UNKNOWN}"
    echo "  Power State: ${power_state:-UNKNOWN}"
    
    # Get UpdateService for Lifecycle Controller
    update_service=$(curl -sk -u "$working_cred" \
        "https://$ip/redfish/v1/UpdateService" 2>/dev/null)
    
    lc_version=$(echo "$update_service" | grep -o '"FirmwareVersion":"[^"]*"' | cut -d'"' -f4)
    echo "  Lifecycle Controller: ${lc_version:-UNKNOWN}"
    
    # Check for available update methods
    echo ""
    echo "  Update Methods Available:"
    echo "$update_service" | grep -o '"HttpPushUri"' >/dev/null && echo "    ✓ HTTP Push URI"
    echo "$update_service" | grep -o '"MultipartHttpPushUri"' >/dev/null && echo "    ✓ Multipart HTTP Push"
    
    echo ""
    echo "  Working Credentials: ${working_cred%%:*}:***"
    echo ""
    
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Discovery Complete - $(date)"
