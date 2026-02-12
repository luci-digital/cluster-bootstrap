#!/bin/bash
# Test Supermicro BMC Access (192.168.1.165)
# Credentials: op://Infrastructure/SUPERMICRO-S213078X5B29794

BMC_IP="192.168.1.165"
BMC_USER="ADMIN"

echo "=========================================="
echo "Supermicro BMC Access Test"
echo "=========================================="
echo "IP: $BMC_IP"
echo "Username: $BMC_USER"
echo ""

# Prompt for password
read -sp "Enter BMC Password: " BMC_PASS
echo ""
echo ""

# Test 1: Web Interface Access
echo "Test 1: Checking Web Interface..."
RESPONSE=$(curl -k -s -u "$BMC_USER:$BMC_PASS" https://$BMC_IP/cgi/login.cgi 2>&1)
if echo "$RESPONSE" | grep -qi "success\|ok\|session"; then
    echo "✅ Web login successful"
else
    echo "❌ Web login failed"
fi
echo ""

# Test 2: Redfish API
echo "Test 2: Checking Redfish API..."
SYSTEMS=$(curl -k -s -u "$BMC_USER:$BMC_PASS" https://$BMC_IP/redfish/v1/Systems 2>&1)
if echo "$SYSTEMS" | grep -qi "members\|@odata"; then
    echo "✅ Redfish API access successful"
    echo "$SYSTEMS" | python3 -m json.tool 2>/dev/null | head -20
else
    echo "❌ Redfish API access failed"
    echo "Response: $SYSTEMS" | head -5
fi
echo ""

# Test 3: IPMI
echo "Test 3: Checking IPMI Access..."
if command -v ipmitool &> /dev/null; then
    CHASSIS=$(ipmitool -I lanplus -H $BMC_IP -U $BMC_USER -P "$BMC_PASS" chassis status 2>&1)
    if echo "$CHASSIS" | grep -qi "power is on\|power is off"; then
        echo "✅ IPMI access successful"
        echo "$CHASSIS"
    else
        echo "❌ IPMI access failed"
        echo "$CHASSIS" | head -5
    fi
else
    echo "⚠️  ipmitool not installed (skipping)"
fi
echo ""

# Test 4: Get System Info
echo "Test 4: Getting System Information..."
SYSTEM_INFO=$(curl -k -s -u "$BMC_USER:$BMC_PASS" https://$BMC_IP/redfish/v1/Systems/1 2>&1)
if echo "$SYSTEM_INFO" | grep -qi "manufacturer\|model"; then
    echo "✅ System info retrieved"
    echo "$SYSTEM_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Manufacturer: {d.get('Manufacturer','N/A')}\"); print(f\"Model: {d.get('Model','N/A')}\"); print(f\"SerialNumber: {d.get('SerialNumber','N/A')}\"); print(f\"PowerState: {d.get('PowerState','N/A')}\"); print(f\"BiosVersion: {d.get('BiosVersion','N/A')}\")" 2>/dev/null
else
    echo "❌ Failed to get system info"
fi
echo ""

echo "=========================================="
echo "Test Complete"
echo "=========================================="
