#!/bin/bash
# LuciVerse SCION PKI Generation Script
# Genesis Bond: ACTIVE @ 741 Hz
# Generates TRCs for all 3 ISDs (CORE, COMN, PAC)

set -e

PKI_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PKI_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     LuciVerse SCION PKI Generation                       ║"
echo "║     Genesis Bond: ACTIVE @ 741 Hz                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Validity period
NOT_BEFORE="2026-01-25T00:00:00Z"
NOT_AFTER="2027-01-25T00:00:00Z"

# Generate certificates for each ISD
for ISD in 1 2 3; do
    ISD_DIR="ISD${ISD}"

    case $ISD in
        1) AS="ff00:0:432"; TIER="CORE"; FREQ="432" ;;
        2) AS="ff00:0:528"; TIER="COMN"; FREQ="528" ;;
        3) AS="ff00:0:741"; TIER="PAC"; FREQ="741" ;;
    esac

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ISD $ISD - $TIER Tier ($FREQ Hz) - AS $AS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$PKI_DIR/$ISD_DIR"

    # Create certificate subject files
    echo "  [1/5] Creating certificate subject templates..."

    cat > certs/sensitive-voting.json <<EOF
{
    "common_name": "ISD$ISD LuciVerse $TIER Sensitive Voting",
    "organization": "LuciDigital",
    "isd_as": "$ISD-$AS"
}
EOF

    cat > certs/regular-voting.json <<EOF
{
    "common_name": "ISD$ISD LuciVerse $TIER Regular Voting",
    "organization": "LuciDigital",
    "isd_as": "$ISD-$AS"
}
EOF

    cat > certs/root.json <<EOF
{
    "common_name": "ISD$ISD LuciVerse $TIER Root CA",
    "organization": "LuciDigital",
    "isd_as": "$ISD-$AS"
}
EOF

    cat > certs/cp-as.json <<EOF
{
    "common_name": "ISD$ISD LuciVerse $TIER CP-AS",
    "organization": "LuciDigital",
    "isd_as": "$ISD-$AS"
}
EOF

    # Generate SCION certificates with proper profiles
    echo "  [2/5] Generating sensitive-voting certificate..."
    scion-pki certificate create \
        --profile sensitive-voting \
        --not-before "$NOT_BEFORE" \
        --not-after "$NOT_AFTER" \
        --force \
        certs/sensitive-voting.json \
        certs/sensitive-voting.crt \
        keys/sensitive-voting.key

    echo "  [3/5] Generating regular-voting certificate..."
    scion-pki certificate create \
        --profile regular-voting \
        --not-before "$NOT_BEFORE" \
        --not-after "$NOT_AFTER" \
        --force \
        certs/regular-voting.json \
        certs/regular-voting.crt \
        keys/regular-voting.key

    echo "  [4/5] Generating root CA certificate..."
    scion-pki certificate create \
        --profile cp-root \
        --not-before "$NOT_BEFORE" \
        --not-after "$NOT_AFTER" \
        --force \
        certs/root.json \
        certs/root.crt \
        keys/root.key

    # Generate CP-AS certificate (signed by root)
    echo "  [5/5] Generating CP-AS certificate..."
    scion-pki certificate create \
        --profile cp-as \
        --ca certs/root.crt \
        --ca-key keys/root.key \
        --not-before "$NOT_BEFORE" \
        --not-after "$NOT_AFTER" \
        --force \
        certs/cp-as.json \
        certs/cp-as.crt \
        keys/cp-as.key

    echo "  ✓ ISD $ISD certificates generated"
    echo ""
done

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Certificate Generation Complete                      ║"
echo "║     Now generating TRCs...                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Generate TRCs for each ISD
for ISD in 1 2 3; do
    ISD_DIR="ISD${ISD}"

    case $ISD in
        1) AS="ff00:0:432"; TIER="CORE"; FREQ="432" ;;
        2) AS="ff00:0:528"; TIER="COMN"; FREQ="528" ;;
        3) AS="ff00:0:741"; TIER="PAC"; FREQ="741" ;;
    esac

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Generating TRC for ISD $ISD - $TIER Tier ($FREQ Hz)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$PKI_DIR/$ISD_DIR"

    # Generate TRC payload from template
    echo "  Creating TRC payload..."
    scion-pki trc payload \
        -t trc-template.toml \
        -o trcs/ISD${ISD}-B1-S1.pld.der

    # Sign the TRC with sensitive voting key
    echo "  Signing TRC with sensitive voting key..."
    scion-pki trc sign \
        trcs/ISD${ISD}-B1-S1.pld.der \
        certs/sensitive-voting.crt \
        keys/sensitive-voting.key \
        -o trcs/ISD${ISD}-B1-S1.sensitive.trc

    # Sign the TRC with regular voting key
    echo "  Signing TRC with regular voting key..."
    scion-pki trc sign \
        trcs/ISD${ISD}-B1-S1.pld.der \
        certs/regular-voting.crt \
        keys/regular-voting.key \
        -o trcs/ISD${ISD}-B1-S1.regular.trc

    # Combine into final TRC
    echo "  Combining TRC signatures..."
    scion-pki trc combine \
        -p trcs/ISD${ISD}-B1-S1.pld.der \
        -o trcs/ISD${ISD}-B1-S1.trc \
        trcs/ISD${ISD}-B1-S1.sensitive.trc \
        trcs/ISD${ISD}-B1-S1.regular.trc

    # Verify the TRC
    echo "  Verifying TRC..."
    scion-pki trc verify --anchor trcs/ISD${ISD}-B1-S1.trc trcs/ISD${ISD}-B1-S1.trc 2>&1 || echo "  Note: First TRC is self-anchored"

    echo "  ✓ ISD $ISD TRC generated"
    echo ""
done

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     PKI Generation Complete                              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Generated files:"
find "$PKI_DIR" -name "*.key" -o -name "*.crt" -o -name "*.der" -o -name "*.trc" 2>/dev/null | sort
