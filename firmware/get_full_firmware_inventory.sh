#!/bin/bash
# Get complete firmware inventory including Lifecycle Controller

declare -A SERVERS
SERVERS=(
    ["R730_ESXi5"]="192.168.1.32:root:calvin"
    ["R720_tron"]="192.168.1.10:root:calvin"
)

for server_name in "${!SERVERS[@]}"; do
    IFS=':' read -r ip user pass <<< "${SERVERS[$server_name]}"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$server_name ($ip) - FULL FIRMWARE LIST"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get all firmware entries
    curl -sk -u "$user:$pass" \
        "https://$ip/redfish/v1/UpdateService/FirmwareInventory" 2>/dev/null | \
        grep -o '"@odata.id":"[^"]*FirmwareInventory[^"]*"' | \
        cut -d'"' -f4 | while read -r fw_uri; do
        
        fw_detail=$(curl -sk -u "$user:$pass" "https://$ip$fw_uri" 2>/dev/null)
        
        name=$(echo "$fw_detail" | grep -o '"Name":"[^"]*"' | head -1 | cut -d'"' -f4)
        version=$(echo "$fw_detail" | grep -o '"Version":"[^"]*"' | head -1 | cut -d'"' -f4)
        
        # Only show if we got valid data
        if [ -n "$name" ] && [ -n "$version" ]; then
            printf "  %-50s %s\n" "$name" "$version"
        fi
    done
    
    echo ""
done
