#!/bin/bash
# A-Tune CXL auto-setup script
# Called by A-Tune when luciverse-cxl-memory profile is activated
# Safe to run on non-CXL hardware (exits gracefully)

set -euo pipefail

CXL_STATUS_DIR="/opt/luciverse/cxl"
LOG="/var/log/luciverse-cxl-setup.log"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"
}

# Check if CXL devices exist
CXL_DEVICE_COUNT=$(cxl list 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(len(d) if isinstance(d, list) else 1)
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$CXL_DEVICE_COUNT" -eq 0 ]; then
    log "No CXL devices detected. Scaffolding mode only."
    exit 0
fi

log "Detected ${CXL_DEVICE_COUNT} CXL device(s). Configuring..."

# Enumerate CXL memory devices
cxl list -M > "${CXL_STATUS_DIR}/memdevs.json" 2>/dev/null || true

# Check for CXL NUMA nodes
CXL_NUMA_NODES=$(lsblk -o NUMA 2>/dev/null | sort -u | wc -l || echo "0")
log "NUMA nodes visible: ${CXL_NUMA_NODES}"

# Configure NUMA balancing for CXL
if [ -f /proc/sys/vm/numa_balancing ]; then
    echo 1 > /proc/sys/vm/numa_balancing
    log "NUMA balancing enabled"
fi

# Set watermark boost for CXL memory pressure handling
if [ -f /proc/sys/vm/watermark_boost_factor ]; then
    echo 15000 > /proc/sys/vm/watermark_boost_factor
    log "Watermark boost factor set to 15000"
fi

# Configure transparent hugepages for CXL regions
if [ -d /sys/kernel/mm/transparent_hugepage ]; then
    echo "madvise" > /sys/kernel/mm/transparent_hugepage/enabled
    log "THP set to madvise mode"
fi

# Update hardware status
cat > "${CXL_STATUS_DIR}/hardware-status.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$(hostname)",
  "cxl_devices_detected": ${CXL_DEVICE_COUNT},
  "cxl_modules_loaded": $(lsmod | grep -c cxl 2>/dev/null || echo 0),
  "kernel_version": "$(uname -r)",
  "cxl_cli_version": "$(cxl --version 2>/dev/null || echo 'not installed')",
  "numa_nodes": ${CXL_NUMA_NODES},
  "readiness": "active"
}
EOF

log "CXL setup complete. Status written to ${CXL_STATUS_DIR}/hardware-status.json"
