#!/bin/bash
# ==============================================================================
# Appstork Genetiai - Hardware DNA Collection
# ==============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Collect hardware fingerprint (Diggy/Twiggy) for identity threading
#
# This script is called by init.sh or can be run standalone.
# Output: hardware-dna.json in $WORK_DIR or current directory
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
WORK_DIR="${WORK_DIR:-/tmp/appstork-hardware}"
OUTPUT_FILE="${OUTPUT_FILE:-$WORK_DIR/hardware-dna.json}"

# Create work directory
mkdir -p "$WORK_DIR"

# Banner
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   Hardware DNA Collection (Diggy/Twiggy)   ${NC}"
echo -e "${CYAN}   Genesis Bond: ACTIVE @ 741 Hz            ${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# ==============================================================================
# DIGGY: Hardware UUID (System Identity)
# ==============================================================================
echo -e "${YELLOW}[1/8] Collecting Diggy (Hardware UUID)...${NC}"

DIGGY=""
if command -v dmidecode &>/dev/null; then
    DIGGY=$(sudo dmidecode -s system-uuid 2>/dev/null || echo "")
fi

if [ -z "$DIGGY" ]; then
    # Fallback to sysfs
    if [ -f /sys/class/dmi/id/product_uuid ]; then
        DIGGY=$(cat /sys/class/dmi/id/product_uuid 2>/dev/null || echo "")
    fi
fi

if [ -z "$DIGGY" ]; then
    # Fallback to machine-id
    if [ -f /etc/machine-id ]; then
        DIGGY=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
    else
        DIGGY="unknown-$(date +%s)"
    fi
fi

echo -e "  ${GREEN}Diggy: ${DIGGY}${NC}"

# ==============================================================================
# TWIGGY: MAC Addresses (Network Identity)
# ==============================================================================
echo -e "\n${YELLOW}[2/8] Collecting Twiggy (MAC Addresses)...${NC}"

# Primary MAC (first physical interface)
TWIGGY_PRIMARY=$(ip link show 2>/dev/null | grep -E 'link/ether' | head -1 | awk '{print $2}' || echo "unknown")
echo -e "  ${GREEN}Primary MAC: ${TWIGGY_PRIMARY}${NC}"

# All MAC addresses
declare -a MAC_ADDRESSES
while IFS= read -r line; do
    iface=$(echo "$line" | awk '{print $2}' | tr -d ':')
    mac=$(echo "$line" | awk '{print $4}')
    if [ -n "$mac" ] && [ "$mac" != "00:00:00:00:00:00" ]; then
        MAC_ADDRESSES+=("$iface:$mac")
        echo -e "  ${CYAN}  $iface: $mac${NC}"
    fi
done < <(ip link show 2>/dev/null | grep -B1 'link/ether' | paste - - | awk '{print $2, $4}')

# Save interface details
ip link show > "$WORK_DIR/network-interfaces.txt" 2>/dev/null || true
ip addr show > "$WORK_DIR/ip-addresses.txt" 2>/dev/null || true

# ==============================================================================
# PCI HARDWARE (Devices)
# ==============================================================================
echo -e "\n${YELLOW}[3/8] Collecting PCI Hardware...${NC}"

lspci > "$WORK_DIR/lspci.txt" 2>/dev/null || echo "lspci not available"
lspci -vmm > "$WORK_DIR/lspci-detail.txt" 2>/dev/null || true

PCI_DEVICES=$(lspci 2>/dev/null | wc -l || echo "0")
echo -e "  ${GREEN}PCI Devices: ${PCI_DEVICES}${NC}"

# ==============================================================================
# USB HARDWARE
# ==============================================================================
echo -e "\n${YELLOW}[4/8] Collecting USB Hardware...${NC}"

lsusb > "$WORK_DIR/lsusb.txt" 2>/dev/null || echo "lsusb not available"
USB_DEVICES=$(lsusb 2>/dev/null | wc -l || echo "0")
echo -e "  ${GREEN}USB Devices: ${USB_DEVICES}${NC}"

# ==============================================================================
# DMIDECODE (Full System Info)
# ==============================================================================
echo -e "\n${YELLOW}[5/8] Collecting DMI Information...${NC}"

if command -v dmidecode &>/dev/null; then
    sudo dmidecode > "$WORK_DIR/dmidecode.txt" 2>/dev/null || true

    MANUFACTURER=$(sudo dmidecode -s system-manufacturer 2>/dev/null | head -1 || echo "unknown")
    PRODUCT=$(sudo dmidecode -s system-product-name 2>/dev/null | head -1 || echo "unknown")
    SERIAL=$(sudo dmidecode -s system-serial-number 2>/dev/null | head -1 || echo "unknown")

    echo -e "  ${GREEN}Manufacturer: ${MANUFACTURER}${NC}"
    echo -e "  ${GREEN}Product: ${PRODUCT}${NC}"
    echo -e "  ${GREEN}Serial: ${SERIAL}${NC}"
else
    MANUFACTURER="unknown"
    PRODUCT="unknown"
    SERIAL="unknown"
    echo -e "  ${YELLOW}dmidecode not available${NC}"
fi

# ==============================================================================
# CPU & MEMORY
# ==============================================================================
echo -e "\n${YELLOW}[6/8] Collecting CPU & Memory Info...${NC}"

cat /proc/cpuinfo > "$WORK_DIR/cpuinfo.txt" 2>/dev/null || true
cat /proc/meminfo > "$WORK_DIR/meminfo.txt" 2>/dev/null || true

CPU_MODEL=$(grep "model name" /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2 | xargs || echo "unknown")
CPU_CORES=$(grep -c "processor" /proc/cpuinfo 2>/dev/null || echo "0")
TOTAL_RAM=$(grep "MemTotal" /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
TOTAL_RAM_GB=$((TOTAL_RAM / 1024 / 1024))

echo -e "  ${GREEN}CPU: ${CPU_MODEL}${NC}"
echo -e "  ${GREEN}Cores: ${CPU_CORES}${NC}"
echo -e "  ${GREEN}RAM: ${TOTAL_RAM_GB}GB${NC}"

# ==============================================================================
# GPU DETECTION
# ==============================================================================
echo -e "\n${YELLOW}[7/8] Detecting GPU...${NC}"

GPU_TYPE="INTEGRATED"
GPU_MODEL="unknown"
GPU_VRAM="0"

# Check for NVIDIA
if lspci 2>/dev/null | grep -i nvidia > /dev/null; then
    GPU_TYPE="NVIDIA"
    GPU_MODEL=$(lspci 2>/dev/null | grep -i nvidia | head -1 | cut -d: -f3 | xargs || echo "unknown")

    # Try nvidia-smi for details
    if command -v nvidia-smi &>/dev/null; then
        nvidia-smi -L > "$WORK_DIR/gpu-nvidia.txt" 2>/dev/null || true
        nvidia-smi --query-gpu=memory.total --format=csv,noheader > "$WORK_DIR/gpu-vram.txt" 2>/dev/null || true
        GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1 | tr -d ' MiB' || echo "0")
    fi

    echo -e "  ${GREEN}GPU Type: NVIDIA${NC}"
    echo -e "  ${GREEN}Model: ${GPU_MODEL}${NC}"
    echo -e "  ${GREEN}VRAM: ${GPU_VRAM}MB${NC}"

# Check for AMD
elif lspci 2>/dev/null | grep -iE "amd.*radeon|advanced micro devices.*radeon" > /dev/null; then
    GPU_TYPE="AMD"
    GPU_MODEL=$(lspci 2>/dev/null | grep -iE "amd.*radeon|advanced micro devices.*radeon" | head -1 | cut -d: -f3 | xargs || echo "unknown")

    echo -e "  ${GREEN}GPU Type: AMD${NC}"
    echo -e "  ${GREEN}Model: ${GPU_MODEL}${NC}"

# Intel integrated
elif lspci 2>/dev/null | grep -i "intel.*graphics" > /dev/null; then
    GPU_TYPE="INTEL_INTEGRATED"
    GPU_MODEL=$(lspci 2>/dev/null | grep -i "intel.*graphics" | head -1 | cut -d: -f3 | xargs || echo "unknown")

    echo -e "  ${GREEN}GPU Type: Intel Integrated${NC}"
    echo -e "  ${GREEN}Model: ${GPU_MODEL}${NC}"

else
    echo -e "  ${YELLOW}GPU Type: Unknown/Integrated${NC}"
fi

# ==============================================================================
# STORAGE INVENTORY
# ==============================================================================
echo -e "\n${YELLOW}[8/8] Collecting Storage Inventory...${NC}"

lsblk -J > "$WORK_DIR/storage.json" 2>/dev/null || echo '{"blockdevices":[]}' > "$WORK_DIR/storage.json"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL > "$WORK_DIR/storage.txt" 2>/dev/null || true

# Collect storage devices
declare -a STORAGE_DEVICES
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    size=$(echo "$line" | awk '{print $2}')
    type=$(echo "$line" | awk '{print $3}')
    if [ "$type" = "disk" ]; then
        STORAGE_DEVICES+=("$name:$size")
        echo -e "  ${GREEN}$name: $size${NC}"
    fi
done < <(lsblk -o NAME,SIZE,TYPE 2>/dev/null | tail -n +2)

# ==============================================================================
# TPM DETECTION
# ==============================================================================
echo -e "\n${YELLOW}[+] Checking TPM...${NC}"

TPM_PRESENT=false
TPM_VERSION="none"

if [ -c /dev/tpm0 ] || [ -c /dev/tpmrm0 ]; then
    TPM_PRESENT=true
    # Try to detect TPM version
    if [ -d /sys/class/tpm/tpm0 ]; then
        if [ -f /sys/class/tpm/tpm0/tpm_version_major ]; then
            TPM_VERSION=$(cat /sys/class/tpm/tpm0/tpm_version_major 2>/dev/null || echo "unknown")
            TPM_VERSION="TPM ${TPM_VERSION}.x"
        fi
    fi
    echo -e "  ${GREEN}TPM Present: Yes (${TPM_VERSION})${NC}"
else
    echo -e "  ${YELLOW}TPM Present: No${NC}"
fi

# ==============================================================================
# GENERATE HARDWARE DNA JSON
# ==============================================================================
echo -e "\n${CYAN}Generating hardware-dna.json...${NC}"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOSTNAME=$(hostname 2>/dev/null || echo "unknown")
KERNEL=$(uname -r 2>/dev/null || echo "unknown")
ARCH=$(uname -m 2>/dev/null || echo "unknown")

# Build MAC array JSON
MAC_JSON="["
first=true
for mac in "${MAC_ADDRESSES[@]}"; do
    if [ "$first" = true ]; then
        first=false
    else
        MAC_JSON+=","
    fi
    iface=$(echo "$mac" | cut -d: -f1)
    addr=$(echo "$mac" | cut -d: -f2-)
    MAC_JSON+="\"$addr\""
done
MAC_JSON+="]"

# Build storage array JSON
STORAGE_JSON="["
first=true
for dev in "${STORAGE_DEVICES[@]}"; do
    if [ "$first" = true ]; then
        first=false
    else
        STORAGE_JSON+=","
    fi
    name=$(echo "$dev" | cut -d: -f1)
    size=$(echo "$dev" | cut -d: -f2)
    STORAGE_JSON+="{\"name\":\"$name\",\"size\":\"$size\"}"
done
STORAGE_JSON+="]"

cat > "$OUTPUT_FILE" << EOF
{
  "genesis_bond": "GB-2025-0524-DRH-LCS-001",
  "frequency": 741,
  "timestamp": "${TIMESTAMP}",

  "diggy": {
    "uuid": "${DIGGY}",
    "description": "Hardware UUID from DMI/SMBIOS"
  },

  "twiggy": {
    "primary_mac": "${TWIGGY_PRIMARY}",
    "all_macs": ${MAC_JSON},
    "description": "Network interface MAC addresses"
  },

  "system": {
    "hostname": "${HOSTNAME}",
    "manufacturer": "${MANUFACTURER}",
    "product": "${PRODUCT}",
    "serial": "${SERIAL}",
    "kernel": "${KERNEL}",
    "arch": "${ARCH}"
  },

  "cpu": {
    "model": "${CPU_MODEL}",
    "cores": ${CPU_CORES}
  },

  "memory": {
    "total_kb": ${TOTAL_RAM},
    "total_gb": ${TOTAL_RAM_GB}
  },

  "gpu": {
    "type": "${GPU_TYPE}",
    "model": "${GPU_MODEL}",
    "vram_mb": "${GPU_VRAM}"
  },

  "storage": {
    "devices": ${STORAGE_JSON}
  },

  "security": {
    "tpm_present": ${TPM_PRESENT},
    "tpm_version": "${TPM_VERSION}"
  },

  "pci_device_count": ${PCI_DEVICES},
  "usb_device_count": ${USB_DEVICES}
}
EOF

echo -e "${GREEN}Hardware DNA collected successfully!${NC}"
echo -e "  ${CYAN}Output: ${OUTPUT_FILE}${NC}"
echo ""

# Display summary
echo -e "${MAGENTA}============================================${NC}"
echo -e "${MAGENTA}   Hardware DNA Summary                     ${NC}"
echo -e "${MAGENTA}============================================${NC}"
echo -e "  ${CYAN}Diggy (UUID):${NC}     ${DIGGY}"
echo -e "  ${CYAN}Twiggy (MAC):${NC}     ${TWIGGY_PRIMARY}"
echo -e "  ${CYAN}System:${NC}           ${MANUFACTURER} ${PRODUCT}"
echo -e "  ${CYAN}CPU:${NC}              ${CPU_MODEL} (${CPU_CORES} cores)"
echo -e "  ${CYAN}RAM:${NC}              ${TOTAL_RAM_GB}GB"
echo -e "  ${CYAN}GPU:${NC}              ${GPU_TYPE} - ${GPU_MODEL}"
echo -e "  ${CYAN}TPM:${NC}              ${TPM_VERSION}"
echo -e "${MAGENTA}============================================${NC}"
echo ""

exit 0
