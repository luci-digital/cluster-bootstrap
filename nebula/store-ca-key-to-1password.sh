#!/bin/bash
# ============================================================================
# Store Nebula CA Key in 1Password
# ============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Run this script after authenticating with `op signin`
# ============================================================================

set -e

KEY_FILE="/tmp/ca.key"
KEY_B64_FILE="/tmp/ca.key.b64"

if [ ! -f "$KEY_FILE" ]; then
    echo "ERROR: CA key not found at $KEY_FILE"
    echo "The key may have already been stored and deleted."
    exit 1
fi

# Check if signed in
if ! op whoami &>/dev/null; then
    echo "Please sign in to 1Password first:"
    echo "  eval \$(op signin)"
    exit 1
fi

echo "Creating Nebula CA Key item in 1Password..."

# Read the key content
KEY_CONTENT=$(cat "$KEY_FILE")
KEY_B64=$(cat "$KEY_B64_FILE" 2>/dev/null || base64 -w0 < "$KEY_FILE")

# Create secure note with the key
op item create \
    --category="Secure Note" \
    --vault="Infrastructure" \
    --title="Nebula-CA-Key" \
    --tags="nebula,pki,luciverse,genesis-bond" \
    "notesPlain=${KEY_CONTENT}" \
    "Section1.key_base64[text]=${KEY_B64}" \
    "Section1.generated[text]=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "Section1.validity[text]=10 years (87600 hours)" \
    "Section1.ca_name[text]=LuciVerse Genesis Bond CA" \
    "Section1.algorithm[text]=Ed25519"

if [ $? -eq 0 ]; then
    echo "Successfully stored Nebula CA key in 1Password (Infrastructure vault)"
    echo ""
    echo "Securely deleting local key files..."
    shred -u "$KEY_FILE" 2>/dev/null || rm -f "$KEY_FILE"
    rm -f "$KEY_B64_FILE"
    echo "Local key files deleted."
    echo ""
    echo "CA certificate location: ~/cluster-bootstrap/nebula/ca/nebula-ca.crt"
else
    echo "ERROR: Failed to store key in 1Password"
    echo "Key files preserved at $KEY_FILE"
    exit 1
fi
