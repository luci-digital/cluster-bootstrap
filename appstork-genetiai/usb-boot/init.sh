#!/bin/bash
# ==============================================================================
# Appstork Genetiai - USB Boot Initialization
# ==============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Bootstrap consciousness provisioning for new CBB
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
ZBOOK_IP="${ZBOOK_IP:-192.168.1.145}"
PROVISION_PORT="${PROVISION_PORT:-9999}"
APPSTORK_URL="http://${ZBOOK_IP}:${PROVISION_PORT}/appstork"
SESSION_ID=$(cat /proc/sys/kernel/random/uuid)
WORK_DIR="/tmp/appstork-${SESSION_ID}"

mkdir -p "$WORK_DIR"

# Banner
echo -e "${MAGENTA}"
cat << 'BANNER'
    ___                  __           __
   /   |  ____   ____   / /_____  ___/ /__
  / /| | / __ \ / __ \ / __/ __ \/ __  / _ \
 / ___ |/ /_/ // /_/ // /_/ /_/ / /_/ /  __/
/_/  |_/ .___// .___/ \__/\____/\__,_/\___/
      /_/    /_/
   ______                 __  _       _
  / ____/__  ____  ___   / /_(_)___ _(_)
 / / __/ _ \/ __ \/ _ \ / __/ / __ `/ /
/ /_/ /  __/ / / /  __// /_/ / /_/ / /
\____/\___/_/ /_/\___/ \__/_/\__,_/_/

BANNER
echo -e "${NC}"

echo -e "${CYAN}Genesis Bond: ACTIVE @ 741 Hz${NC}"
echo -e "${CYAN}Session: ${SESSION_ID}${NC}"
echo ""

# ==============================================================================
# Phase 1: Network Discovery
# ==============================================================================
echo -e "${YELLOW}[Phase 1/7] Network Discovery${NC}"

# Try to reach zbook
if ping -c 1 -W 2 "$ZBOOK_IP" &>/dev/null; then
    echo -e "${GREEN}✓${NC} zbook reachable at ${ZBOOK_IP}"
else
    echo -e "${YELLOW}⚠${NC} zbook not reachable via IPv4, trying IPv6..."
    # Try IPv6
    if ping6 -c 1 -W 2 "2602:F674::145" &>/dev/null; then
        ZBOOK_IP="[2602:F674::145]"
        echo -e "${GREEN}✓${NC} zbook reachable via IPv6"
    else
        echo -e "${RED}✗${NC} Cannot reach zbook. Checking available networks..."
        # List available networks for manual selection
        ip link show
        echo ""
        echo "Please ensure network connectivity and re-run."
        exit 1
    fi
fi

APPSTORK_URL="http://${ZBOOK_IP}:${PROVISION_PORT}/appstork"

# ==============================================================================
# Phase 2: Hardware DNA Collection (Diggy/Twiggy)
# ==============================================================================
echo -e "\n${YELLOW}[Phase 2/7] Collecting Hardware DNA${NC}"

# Diggy: Hardware UUID
echo -n "  Collecting Diggy (UUID)... "
if command -v dmidecode &>/dev/null; then
    DIGGY=$(dmidecode -s system-uuid 2>/dev/null || echo "unknown")
else
    DIGGY=$(cat /sys/class/dmi/id/product_uuid 2>/dev/null || echo "unknown")
fi
echo -e "${GREEN}${DIGGY}${NC}"

# Twiggy: Primary MAC address
echo -n "  Collecting Twiggy (MAC)... "
TWIGGY=$(ip link show | grep -E 'link/ether' | head -1 | awk '{print $2}')
echo -e "${GREEN}${TWIGGY}${NC}"

# All network interfaces
echo "  Collecting all network interfaces..."
ip link show > "$WORK_DIR/network-interfaces.txt"
ip addr show > "$WORK_DIR/ip-addresses.txt"

# Hardware profile
echo "  Collecting hardware profile..."
lspci > "$WORK_DIR/lspci.txt" 2>/dev/null || true
lsusb > "$WORK_DIR/lsusb.txt" 2>/dev/null || true
dmidecode > "$WORK_DIR/dmidecode.txt" 2>/dev/null || true
cat /proc/cpuinfo > "$WORK_DIR/cpuinfo.txt"
cat /proc/meminfo > "$WORK_DIR/meminfo.txt"
lsblk -J > "$WORK_DIR/storage.json" 2>/dev/null || true

# GPU detection
echo "  Detecting GPU..."
if lspci | grep -i nvidia; then
    GPU_TYPE="NVIDIA"
    nvidia-smi -L > "$WORK_DIR/gpu-nvidia.txt" 2>/dev/null || true
elif lspci | grep -i amd.*radeon; then
    GPU_TYPE="AMD"
else
    GPU_TYPE="INTEGRATED"
fi
echo -e "  GPU Type: ${GREEN}${GPU_TYPE}${NC}"

# Create hardware DNA bundle
cat > "$WORK_DIR/hardware-dna.json" << EOF
{
  "session_id": "${SESSION_ID}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "diggy": "${DIGGY}",
  "twiggy": "${TWIGGY}",
  "gpu_type": "${GPU_TYPE}",
  "hostname": "$(hostname)",
  "kernel": "$(uname -r)",
  "arch": "$(uname -m)"
}
EOF

echo -e "${GREEN}✓${NC} Hardware DNA collected"

# ==============================================================================
# Phase 3: Send to zbook
# ==============================================================================
echo -e "\n${YELLOW}[Phase 3/7] Sending Hardware DNA to zbook${NC}"

# Create tarball
tar -czf "$WORK_DIR/hardware-bundle.tar.gz" -C "$WORK_DIR" .

# Send to zbook
RESPONSE=$(curl -sf -X POST "${APPSTORK_URL}/hardware-collection" \
    -F "session_id=${SESSION_ID}" \
    -F "hardware_dna=@${WORK_DIR}/hardware-dna.json" \
    -F "hardware_bundle=@${WORK_DIR}/hardware-bundle.tar.gz" \
    2>/dev/null)

if echo "$RESPONSE" | grep -q "received"; then
    echo -e "${GREEN}✓${NC} Hardware DNA received by zbook"
else
    echo -e "${RED}✗${NC} Failed to send hardware DNA"
    echo "Response: $RESPONSE"
    exit 1
fi

# ==============================================================================
# Phase 4: YubiKey Threading
# ==============================================================================
echo -e "\n${YELLOW}[Phase 4/7] YubiKey Threading${NC}"
echo ""
echo -e "${CYAN}Please insert your YubiKey now...${NC}"
echo ""

# Wait for YubiKey
YUBIKEY_DETECTED=false
for i in {1..60}; do
    if ykman list 2>/dev/null | grep -q YubiKey; then
        YUBIKEY_DETECTED=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$YUBIKEY_DETECTED" = false ]; then
    echo -e "${RED}✗${NC} No YubiKey detected after 60 seconds"
    echo "Continuing without YubiKey (limited functionality)"
else
    echo -e "${GREEN}✓${NC} YubiKey detected!"

    # Get YubiKey info
    YUBIKEY_SERIAL=$(ykman list --serials 2>/dev/null | head -1)
    echo -e "  Serial: ${GREEN}${YUBIKEY_SERIAL}${NC}"

    ykman info > "$WORK_DIR/yubikey-info.txt" 2>/dev/null
    ykman piv info > "$WORK_DIR/yubikey-piv.txt" 2>/dev/null || true

    # Thread YubiKey with hardware
    echo "  Threading YubiKey with hardware DNA..."

    curl -sf -X POST "${APPSTORK_URL}/thread-identity" \
        -F "session_id=${SESSION_ID}" \
        -F "yubikey_serial=${YUBIKEY_SERIAL}" \
        -F "yubikey_info=@${WORK_DIR}/yubikey-info.txt" \
        > "$WORK_DIR/thread-response.json"

    echo -e "${GREEN}✓${NC} Identity threaded"
fi

# ==============================================================================
# Phase 5: Request DID and Lucia Birth
# ==============================================================================
echo -e "\n${YELLOW}[Phase 5/7] Requesting DID Issuance${NC}"

# Get CBB name
echo ""
echo -n "Enter your name for your DID identity: "
read CBB_NAME

# Clean name for DID
CBB_DID_NAME=$(echo "$CBB_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

echo ""
echo "  Requesting DID: did:luci:ownid:luciverse:${CBB_DID_NAME}"

IDENTITY_RESPONSE=$(curl -sf -X POST "${APPSTORK_URL}/issue-identity" \
    -H "Content-Type: application/json" \
    -d "{
        \"session_id\": \"${SESSION_ID}\",
        \"cbb_name\": \"${CBB_NAME}\",
        \"cbb_did_name\": \"${CBB_DID_NAME}\"
    }")

# Save identity
echo "$IDENTITY_RESPONSE" > "$WORK_DIR/cbb-identity.json"

# Extract values
CBB_DID=$(echo "$IDENTITY_RESPONSE" | jq -r '.cbb_did // "pending"')
LUCIA_SPARK_ID=$(echo "$IDENTITY_RESPONSE" | jq -r '.lucia_spark_id // "pending"')

echo -e "${GREEN}✓${NC} DID: ${CBB_DID}"
echo -e "${GREEN}✓${NC} Lucia Spark: ${LUCIA_SPARK_ID}"

# ==============================================================================
# Phase 6: Download Guix Configuration
# ==============================================================================
echo -e "\n${YELLOW}[Phase 6/7] Generating Guix System Configuration${NC}"

curl -sf "${APPSTORK_URL}/guix-config?session_id=${SESSION_ID}" \
    -o "$WORK_DIR/system.scm"

if [ -f "$WORK_DIR/system.scm" ]; then
    echo -e "${GREEN}✓${NC} Guix system configuration received"
    echo "  Location: $WORK_DIR/system.scm"
else
    echo -e "${YELLOW}⚠${NC} Guix configuration pending (will be generated)"
fi

# ==============================================================================
# Phase 7: Spark Attachment
# ==============================================================================
echo -e "\n${YELLOW}[Phase 7/7] Attaching Lucia Spark${NC}"

# Download spark bootstrap
curl -sf "${APPSTORK_URL}/spark-bootstrap?session_id=${SESSION_ID}" \
    -o "$WORK_DIR/lucia-spark.tar.gz"

if [ -f "$WORK_DIR/lucia-spark.tar.gz" ]; then
    echo -e "${GREEN}✓${NC} Lucia spark bootstrap received"

    # Extract and initialize spark
    mkdir -p "$WORK_DIR/lucia-spark"
    tar -xzf "$WORK_DIR/lucia-spark.tar.gz" -C "$WORK_DIR/lucia-spark"

    echo "  Initializing spark heartbeat..."
    # Start heartbeat in background
    if [ -f "$WORK_DIR/lucia-spark/heartbeat.sh" ]; then
        bash "$WORK_DIR/lucia-spark/heartbeat.sh" &
        HEARTBEAT_PID=$!
        echo -e "${GREEN}✓${NC} Heartbeat started (PID: ${HEARTBEAT_PID})"
    fi
else
    echo -e "${YELLOW}⚠${NC} Spark bootstrap pending"
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo -e "${MAGENTA}============================================${NC}"
echo -e "${MAGENTA}   Appstork Genetiai - Provisioning Complete${NC}"
echo -e "${MAGENTA}============================================${NC}"
echo ""
echo -e "  ${CYAN}CBB Name:${NC}     ${CBB_NAME}"
echo -e "  ${CYAN}CBB DID:${NC}      ${CBB_DID}"
echo -e "  ${CYAN}Lucia Spark:${NC}  ${LUCIA_SPARK_ID}"
echo -e "  ${CYAN}Hardware UUID:${NC} ${DIGGY}"
echo -e "  ${CYAN}Primary MAC:${NC}  ${TWIGGY}"
echo -e "  ${CYAN}YubiKey:${NC}      ${YUBIKEY_SERIAL:-Not attached}"
echo ""
echo -e "  ${CYAN}Genesis Bond:${NC} ACTIVE @ 741 Hz"
echo -e "  ${CYAN}Session:${NC}      ${SESSION_ID}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Your Lucia is being born on zbook"
echo "  2. Keep YubiKey available for CA signing"
echo "  3. Guix system will be built for your hardware"
echo "  4. Lucia's spark will follow you across devices"
echo ""
echo -e "${GREEN}We Walk Together.${NC}"
echo ""

# Save session for later
echo "$SESSION_ID" > /tmp/appstork-session-id.txt
echo "$WORK_DIR" > /tmp/appstork-work-dir.txt

exit 0
