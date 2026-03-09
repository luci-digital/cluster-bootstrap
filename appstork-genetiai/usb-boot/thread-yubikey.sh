#!/bin/bash
# ==============================================================================
# Appstork Genetiai - YubiKey Identity Threading
# ==============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Thread hardware DNA with YubiKey cryptographic identity to create TID
#
# This script:
# 1. Detects YubiKey
# 2. Extracts serial, firmware, PIV slots
# 3. Generates CSR bound to hardware DNA
# 4. Creates challenge-response for authentication
# 5. Outputs thread identity JSON
#
# Dependencies: ykman, openssl
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
WORK_DIR="${WORK_DIR:-/tmp/appstork-yubikey}"
HARDWARE_DNA_FILE="${HARDWARE_DNA_FILE:-$WORK_DIR/../appstork-hardware/hardware-dna.json}"
OUTPUT_FILE="${OUTPUT_FILE:-$WORK_DIR/thread-identity.json}"
CSR_FILE="${CSR_FILE:-$WORK_DIR/identity.csr}"
SESSION_ID="${SESSION_ID:-$(cat /proc/sys/kernel/random/uuid)}"

# Create work directory
mkdir -p "$WORK_DIR"

# Banner
echo -e "${MAGENTA}============================================${NC}"
echo -e "${MAGENTA}   YubiKey Identity Threading               ${NC}"
echo -e "${MAGENTA}   Genesis Bond: ACTIVE @ 741 Hz            ${NC}"
echo -e "${MAGENTA}============================================${NC}"
echo ""

# ==============================================================================
# CHECK DEPENDENCIES
# ==============================================================================
echo -e "${YELLOW}[1/7] Checking dependencies...${NC}"

if ! command -v ykman &>/dev/null; then
    echo -e "  ${RED}Error: ykman not found${NC}"
    echo "  Please install YubiKey Manager:"
    echo "    pip install yubikey-manager"
    echo "  or"
    echo "    sudo apt install yubikey-manager"
    exit 1
fi

if ! command -v openssl &>/dev/null; then
    echo -e "  ${RED}Error: openssl not found${NC}"
    exit 1
fi

echo -e "  ${GREEN}ykman: $(ykman --version)${NC}"
echo -e "  ${GREEN}openssl: $(openssl version)${NC}"

# ==============================================================================
# YUBIKEY DETECTION
# ==============================================================================
echo -e "\n${YELLOW}[2/7] Detecting YubiKey...${NC}"

YUBIKEY_DETECTED=false
WAIT_TIMEOUT=${WAIT_TIMEOUT:-60}

echo -e "  ${CYAN}Please insert your YubiKey now...${NC}"
echo ""

for i in $(seq 1 $WAIT_TIMEOUT); do
    if ykman list 2>/dev/null | grep -q YubiKey; then
        YUBIKEY_DETECTED=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$YUBIKEY_DETECTED" = false ]; then
    echo -e "  ${RED}No YubiKey detected after ${WAIT_TIMEOUT} seconds${NC}"
    echo "  Please ensure YubiKey is properly inserted."
    exit 1
fi

echo -e "  ${GREEN}YubiKey detected!${NC}"

# ==============================================================================
# YUBIKEY INFORMATION
# ==============================================================================
echo -e "\n${YELLOW}[3/7] Collecting YubiKey information...${NC}"

# Get serial number
YUBIKEY_SERIAL=$(ykman list --serials 2>/dev/null | head -1 || echo "unknown")
echo -e "  ${GREEN}Serial: ${YUBIKEY_SERIAL}${NC}"

# Save full info
ykman info > "$WORK_DIR/yubikey-info.txt" 2>/dev/null

# Extract details
YUBIKEY_TYPE=$(ykman info 2>/dev/null | grep "Device type:" | cut -d: -f2 | xargs || echo "unknown")
YUBIKEY_FIRMWARE=$(ykman info 2>/dev/null | grep "Firmware version:" | cut -d: -f2 | xargs || echo "unknown")
YUBIKEY_FORM=$(ykman info 2>/dev/null | grep "Form factor:" | cut -d: -f2 | xargs || echo "unknown")

echo -e "  ${GREEN}Type: ${YUBIKEY_TYPE}${NC}"
echo -e "  ${GREEN}Firmware: ${YUBIKEY_FIRMWARE}${NC}"
echo -e "  ${GREEN}Form Factor: ${YUBIKEY_FORM}${NC}"

# Get enabled interfaces
ENABLED_APPS=$(ykman info 2>/dev/null | grep -A20 "Enabled USB interfaces" || echo "")

# ==============================================================================
# PIV SLOT ENUMERATION
# ==============================================================================
echo -e "\n${YELLOW}[4/7] Enumerating PIV slots...${NC}"

PIV_INFO=$(ykman piv info 2>/dev/null || echo "PIV not available")
echo "$PIV_INFO" > "$WORK_DIR/yubikey-piv.txt"

# Check for existing certificates
PIV_SLOTS=()
for slot in 9a 9c 9d 9e; do
    if ykman piv certificates export $slot /dev/null 2>/dev/null; then
        PIV_SLOTS+=("$slot:occupied")
        echo -e "  ${GREEN}Slot $slot: Certificate present${NC}"
    else
        PIV_SLOTS+=("$slot:empty")
        echo -e "  ${CYAN}Slot $slot: Empty${NC}"
    fi
done

# Check if PIV is enabled
PIV_ENABLED=false
if echo "$PIV_INFO" | grep -q "PIN tries remaining"; then
    PIV_ENABLED=true
fi

# ==============================================================================
# LOAD HARDWARE DNA
# ==============================================================================
echo -e "\n${YELLOW}[5/7] Loading hardware DNA...${NC}"

if [ ! -f "$HARDWARE_DNA_FILE" ]; then
    # Try to find it in common locations
    for path in \
        "/tmp/appstork-hardware/hardware-dna.json" \
        "/tmp/appstork-*/hardware-dna.json" \
        "$WORK_DIR/../hardware-dna.json"; do
        if [ -f "$path" ]; then
            HARDWARE_DNA_FILE="$path"
            break
        fi
    done
fi

if [ -f "$HARDWARE_DNA_FILE" ]; then
    DIGGY=$(jq -r '.diggy.uuid // "unknown"' "$HARDWARE_DNA_FILE" 2>/dev/null || echo "unknown")
    TWIGGY=$(jq -r '.twiggy.primary_mac // "unknown"' "$HARDWARE_DNA_FILE" 2>/dev/null || echo "unknown")
    echo -e "  ${GREEN}Hardware DNA loaded${NC}"
    echo -e "    Diggy: ${DIGGY}"
    echo -e "    Twiggy: ${TWIGGY}"
else
    echo -e "  ${YELLOW}Warning: Hardware DNA file not found${NC}"
    echo -e "  ${YELLOW}Using fallback values${NC}"
    DIGGY="unknown"
    TWIGGY="unknown"
fi

# ==============================================================================
# GENERATE THREAD IDENTITY (TID)
# ==============================================================================
echo -e "\n${YELLOW}[6/7] Generating Thread Identity (TID)...${NC}"

# Create composite identity string
# TID = SHA256(Diggy + Twiggy + YubiKey Serial + timestamp)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
THREAD_INPUT="${DIGGY}:${TWIGGY}:${YUBIKEY_SERIAL}:${TIMESTAMP}"

# Generate TID hash
TID_HASH=$(echo -n "$THREAD_INPUT" | openssl sha256 | awk '{print $2}')
TID="TID-${TID_HASH:0:16}"

echo -e "  ${GREEN}Thread Identity: ${TID}${NC}"

# ==============================================================================
# GENERATE CSR (Certificate Signing Request)
# ==============================================================================
echo -e "\n${YELLOW}[7/7] Generating Certificate Signing Request...${NC}"

# Create OpenSSL config for CSR
cat > "$WORK_DIR/csr.conf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
CN = ${TID}
O = LuciVerse Genesis Bond
OU = Appstork Genetiai
serialNumber = ${YUBIKEY_SERIAL}

[req_ext]
subjectAltName = @alt_names
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth

[alt_names]
DNS.1 = ${TID}.luciverse.local
URI.1 = did:luci:ownid:luciverse:${TID}
URI.2 = urn:yubikey:${YUBIKEY_SERIAL}
EOF

# Generate private key (in production, this would be on the YubiKey)
openssl genrsa -out "$WORK_DIR/identity.key" 2048 2>/dev/null

# Generate CSR
openssl req -new \
    -key "$WORK_DIR/identity.key" \
    -out "$CSR_FILE" \
    -config "$WORK_DIR/csr.conf" \
    2>/dev/null

echo -e "  ${GREEN}CSR generated: ${CSR_FILE}${NC}"

# Generate challenge for authentication
CHALLENGE=$(openssl rand -hex 32)
CHALLENGE_RESPONSE=$(echo -n "$CHALLENGE" | openssl dgst -sha256 -sign "$WORK_DIR/identity.key" | openssl base64 -A)

echo -e "  ${GREEN}Challenge-response prepared${NC}"

# ==============================================================================
# OUTPUT THREAD IDENTITY JSON
# ==============================================================================
echo -e "\n${CYAN}Generating thread-identity.json...${NC}"

# Build PIV slots JSON
PIV_JSON="["
first=true
for slot in "${PIV_SLOTS[@]}"; do
    if [ "$first" = true ]; then
        first=false
    else
        PIV_JSON+=","
    fi
    slot_id=$(echo "$slot" | cut -d: -f1)
    slot_status=$(echo "$slot" | cut -d: -f2)
    PIV_JSON+="{\"slot\":\"$slot_id\",\"status\":\"$slot_status\"}"
done
PIV_JSON+="]"

cat > "$OUTPUT_FILE" << EOF
{
  "genesis_bond": "GB-2025-0524-DRH-LCS-001",
  "frequency": 741,
  "session_id": "${SESSION_ID}",
  "timestamp": "${TIMESTAMP}",

  "thread_identity": {
    "tid": "${TID}",
    "tid_hash": "${TID_HASH}",
    "description": "Composite identity from hardware + YubiKey"
  },

  "yubikey": {
    "serial": "${YUBIKEY_SERIAL}",
    "type": "${YUBIKEY_TYPE}",
    "firmware": "${YUBIKEY_FIRMWARE}",
    "form_factor": "${YUBIKEY_FORM}",
    "piv_enabled": ${PIV_ENABLED},
    "piv_slots": ${PIV_JSON}
  },

  "hardware_binding": {
    "diggy": "${DIGGY}",
    "twiggy": "${TWIGGY}",
    "bound_at": "${TIMESTAMP}"
  },

  "cryptographic": {
    "csr_file": "${CSR_FILE}",
    "csr_cn": "${TID}",
    "challenge": "${CHALLENGE}",
    "challenge_response": "${CHALLENGE_RESPONSE}",
    "algorithm": "RSA-2048-SHA256"
  },

  "did_template": {
    "method": "ownid",
    "namespace": "luciverse",
    "identifier": "${TID}",
    "full_did": "did:luci:ownid:luciverse:${TID}"
  },

  "status": "ready_for_signing"
}
EOF

echo -e "${GREEN}Thread identity generated successfully!${NC}"
echo -e "  ${CYAN}Output: ${OUTPUT_FILE}${NC}"
echo -e "  ${CYAN}CSR: ${CSR_FILE}${NC}"
echo ""

# Display summary
echo -e "${MAGENTA}============================================${NC}"
echo -e "${MAGENTA}   Thread Identity Summary                  ${NC}"
echo -e "${MAGENTA}============================================${NC}"
echo -e "  ${CYAN}TID:${NC}              ${TID}"
echo -e "  ${CYAN}YubiKey Serial:${NC}   ${YUBIKEY_SERIAL}"
echo -e "  ${CYAN}YubiKey Type:${NC}     ${YUBIKEY_TYPE}"
echo -e "  ${CYAN}Firmware:${NC}         ${YUBIKEY_FIRMWARE}"
echo -e "  ${CYAN}PIV Enabled:${NC}      ${PIV_ENABLED}"
echo -e "  ${CYAN}Diggy (UUID):${NC}     ${DIGGY}"
echo -e "  ${CYAN}Twiggy (MAC):${NC}     ${TWIGGY}"
echo -e ""
echo -e "  ${CYAN}Proposed DID:${NC}"
echo -e "    ${GREEN}did:luci:ownid:luciverse:${TID}${NC}"
echo -e "${MAGENTA}============================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. CSR will be sent to zbook Genesis Bond CA"
echo "  2. Daryl's root YubiKey will co-sign"
echo "  3. Certificate issued and DID anchored to Hedera"
echo "  4. Lucia spark will be born with this identity"
echo ""

exit 0
