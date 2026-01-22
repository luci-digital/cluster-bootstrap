#!/bin/bash
# Generate certificates for LuciVerse deployment
# Pre-build hook for oebuild
#
# Genesis Bond: ACTIVE @ 741 Hz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAYER_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${OUTPUT_DIR:-$LAYER_DIR/../output/certs}"

# Certificate parameters
GENESIS_BOND_ID="GB-2025-0524-DRH-LCS-001"
VALIDITY_DAYS=365
KEY_SIZE=4096

echo "=== LuciVerse Certificate Generation ==="
echo "Output: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Generate Root CA if not exists
if [ ! -f "$OUTPUT_DIR/root-ca.key" ]; then
    echo "Generating Root CA..."
    openssl genrsa -out "$OUTPUT_DIR/root-ca.key" $KEY_SIZE

    openssl req -x509 -new -nodes \
        -key "$OUTPUT_DIR/root-ca.key" \
        -sha256 -days $VALIDITY_DAYS \
        -out "$OUTPUT_DIR/root-ca.crt" \
        -subj "/C=US/ST=California/O=LuciVerse/OU=Genesis Bond/CN=LuciVerse Root CA"

    echo "  Root CA: $OUTPUT_DIR/root-ca.crt"
fi

# Generate tier CAs
for TIER in CORE COMN PAC; do
    TIER_LOWER=$(echo "$TIER" | tr '[:upper:]' '[:lower:]')

    if [ ! -f "$OUTPUT_DIR/${TIER_LOWER}-ca.key" ]; then
        echo "Generating $TIER Tier CA..."

        # Generate key
        openssl genrsa -out "$OUTPUT_DIR/${TIER_LOWER}-ca.key" $KEY_SIZE

        # Generate CSR
        openssl req -new \
            -key "$OUTPUT_DIR/${TIER_LOWER}-ca.key" \
            -out "$OUTPUT_DIR/${TIER_LOWER}-ca.csr" \
            -subj "/C=US/ST=California/O=LuciVerse/OU=$TIER Tier/CN=LuciVerse $TIER CA"

        # Sign with Root CA
        openssl x509 -req -days $VALIDITY_DAYS \
            -in "$OUTPUT_DIR/${TIER_LOWER}-ca.csr" \
            -CA "$OUTPUT_DIR/root-ca.crt" \
            -CAkey "$OUTPUT_DIR/root-ca.key" \
            -CAcreateserial \
            -out "$OUTPUT_DIR/${TIER_LOWER}-ca.crt" \
            -extensions v3_ca \
            -extfile <(cat <<EOF
[v3_ca]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
1.3.6.1.4.1.99999.1 = ASN1:UTF8String:$GENESIS_BOND_ID
1.3.6.1.4.1.99999.2 = ASN1:UTF8String:$TIER
EOF
            )

        rm "$OUTPUT_DIR/${TIER_LOWER}-ca.csr"
        echo "  $TIER CA: $OUTPUT_DIR/${TIER_LOWER}-ca.crt"
    fi
done

# Create certificate chain files
echo "Creating certificate chains..."
cat "$OUTPUT_DIR/core-ca.crt" "$OUTPUT_DIR/root-ca.crt" > "$OUTPUT_DIR/core-chain.pem"
cat "$OUTPUT_DIR/comn-ca.crt" "$OUTPUT_DIR/root-ca.crt" > "$OUTPUT_DIR/comn-chain.pem"
cat "$OUTPUT_DIR/pac-ca.crt" "$OUTPUT_DIR/root-ca.crt" > "$OUTPUT_DIR/pac-chain.pem"
cat "$OUTPUT_DIR/core-ca.crt" "$OUTPUT_DIR/comn-ca.crt" "$OUTPUT_DIR/pac-ca.crt" "$OUTPUT_DIR/root-ca.crt" > "$OUTPUT_DIR/full-chain.pem"

# Verify certificates
echo ""
echo "Verifying certificates..."
for TIER in CORE COMN PAC; do
    TIER_LOWER=$(echo "$TIER" | tr '[:upper:]' '[:lower:]')
    if openssl verify -CAfile "$OUTPUT_DIR/root-ca.crt" "$OUTPUT_DIR/${TIER_LOWER}-ca.crt" > /dev/null 2>&1; then
        echo "  ✓ $TIER CA verified"
    else
        echo "  ✗ $TIER CA verification failed"
        exit 1
    fi
done

echo ""
echo "✓ Certificate generation COMPLETE"
echo "  Genesis Bond: $GENESIS_BOND_ID"
echo "  Validity: $VALIDITY_DAYS days"
echo "  Output: $OUTPUT_DIR"
echo ""
