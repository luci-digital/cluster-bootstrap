#!/bin/bash
# Deep dive into Lifecycle Controller versions

declare -A SERVERS
SERVERS=(
    ["R720_tron"]="192.168.1.10:root:calvin"
    ["R730_ORION"]="192.168.1.2:root:calvin"
    ["R730_ESXi5"]="192.168.1.32:root:calvin"
    ["R730_CSDR282"]="192.168.1.3:root:Newdaryl24!"
    ["R730_1JF6Q22"]="192.168.1.31:root:calvin"
    ["R730_1JF7Q22"]="192.168.1.33:root:Newdaryl24!"
)

echo "=== LIFECYCLE CONTROLLER DEEP INSPECTION ==="
echo ""

for server_name in "${!SERVERS[@]}"; do
    IFS=':' read -r ip user pass <<< "${SERVERS[$server_name]}"
    
    echo "━━━ $server_name ($ip) ━━━"
    
    # Method 1: Check UpdateService FirmwareInventory
    echo "Checking Firmware Inventory..."
    firmware_inventory=$(curl -sk -u "$user:$pass" \
        "https://$ip/redfish/v1/UpdateService/FirmwareInventory" 2>/dev/null)
    
    # Look for Lifecycle Controller entries
    lc_entries=$(echo "$firmware_inventory" | grep -o '"@odata.id":"[^"]*Lifecycle[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$lc_entries" ]; then
        for entry in $lc_entries; do
            echo "  Found LC entry: $entry"
            lc_detail=$(curl -sk -u "$user:$pass" "https://$ip$entry" 2>/dev/null)
            lc_version=$(echo "$lc_detail" | grep -o '"Version":"[^"]*"' | cut -d'"' -f4)
            lc_name=$(echo "$lc_detail" | grep -o '"Name":"[^"]*"' | cut -d'"' -f4)
            echo "    Name: $lc_name"
            echo "    Version: $lc_version"
        done
    else
        echo "  No Lifecycle Controller entries found in inventory"
    fi
    
    # Method 2: Check direct Manager attributes
    echo ""
    echo "Checking Manager Attributes..."
    manager=$(curl -sk -u "$user:$pass" \
        "https://$ip/redfish/v1/Managers/iDRAC.Embedded.1" 2>/dev/null)
    
    # Get full firmware version info
    echo "$manager" | grep -A 2 "FirmwareVersion" | head -5
    
    # Method 3: Check Oem Dell attributes
    echo ""
    echo "Checking Dell OEM Attributes..."
    oem_info=$(echo "$manager" | grep -A 20 '"Oem"')
    echo "$oem_info" | grep -i "lifecycle" || echo "  No OEM Lifecycle info found"
    
    echo ""
    
done
