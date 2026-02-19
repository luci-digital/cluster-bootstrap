#!/bin/bash
# CXL Device Health Monitor
# Run periodically via cron or systemd timer
# Reports CXL device status to hardware probe endpoint

set -euo pipefail

CXL_STATUS_DIR="/opt/luciverse/cxl"
PROBE_URL="http://10.0.0.1:9999/hardware-probe"

# Quick check: any CXL devices?
if ! command -v cxl &>/dev/null; then
    exit 0  # cxl-cli not installed, skip
fi

CXL_DEVICES=$(cxl list 2>/dev/null || echo "[]")
DEVICE_COUNT=$(echo "$CXL_DEVICES" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d) if isinstance(d, list) else (1 if d else 0))
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$DEVICE_COUNT" -eq 0 ]; then
    exit 0  # No devices, nothing to monitor
fi

# Collect health data
HEALTH_STATUS="ok"
ALERTS=""

# Check for CXL errors in dmesg
CXL_ERRORS=$(dmesg | grep -ci "cxl.*error" 2>/dev/null || echo "0")
if [ "$CXL_ERRORS" -gt 0 ]; then
    HEALTH_STATUS="warning"
    ALERTS="cxl_dmesg_errors=${CXL_ERRORS}"
fi

# Check CXL memory regions
CXL_REGIONS=$(cxl list -R 2>/dev/null || echo "[]")
REGION_COUNT=$(echo "$CXL_REGIONS" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d) if isinstance(d, list) else (1 if d else 0))
except:
    print(0)
" 2>/dev/null || echo "0")

# Write status
mkdir -p "$CXL_STATUS_DIR"
cat > "${CXL_STATUS_DIR}/health.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$(hostname)",
  "health": "${HEALTH_STATUS}",
  "devices": ${DEVICE_COUNT},
  "regions": ${REGION_COUNT},
  "dmesg_errors": ${CXL_ERRORS},
  "alerts": "${ALERTS}"
}
EOF

# Report to probe endpoint
curl -sf "$PROBE_URL" \
    -d "hostname=$(hostname)&cxl_health=${HEALTH_STATUS}&cxl_devices=${DEVICE_COUNT}&cxl_regions=${REGION_COUNT}" \
    2>/dev/null || true
