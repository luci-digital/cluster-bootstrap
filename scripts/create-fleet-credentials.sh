#!/bin/bash
# ============================================================================
# Create Dell Fleet Credentials in 1Password
# ============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Run this script interactively to create the required credentials
# ============================================================================

set -e

VAULT="Infrastructure"

echo "============================================"
echo "Dell Fleet Credential Setup"
echo "============================================"
echo ""

# Check if already signed in
if ! op whoami &>/dev/null; then
    echo "Please sign in to 1Password CLI..."
    eval $(op signin)
fi

echo "Signed in as: $(op whoami --format=json | jq -r '.email')"
echo ""

# Generate secure passwords
ROOT_PASS=$(op item get "Dell-Fleet-Root" --vault "$VAULT" --fields password 2>/dev/null || echo "")
USER_PASS=$(op item get "Dell-Fleet-User" --vault "$VAULT" --fields password 2>/dev/null || echo "")

if [ -n "$ROOT_PASS" ]; then
    echo "✓ Dell-Fleet-Root already exists"
else
    echo "Creating Dell-Fleet-Root..."
    ROOT_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
    op item create \
        --category=login \
        --title="Dell-Fleet-Root" \
        --vault="$VAULT" \
        --tags="fleet,dell,root,pxe" \
        "username=root" \
        "password=$ROOT_PASS" \
        "notes=Root credentials for Dell Fleet PXE provisioned servers. Used by kickstart credential-inject.sh script."
    echo "✓ Dell-Fleet-Root created"
fi

if [ -n "$USER_PASS" ]; then
    echo "✓ Dell-Fleet-User already exists"
else
    echo "Creating Dell-Fleet-User..."
    USER_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
    op item create \
        --category=login \
        --title="Dell-Fleet-User" \
        --vault="$VAULT" \
        --tags="fleet,dell,user,pxe,daryl" \
        "username=daryl" \
        "password=$USER_PASS" \
        "notes=User 'daryl' credentials for Dell Fleet PXE provisioned servers. Used by kickstart credential-inject.sh script."
    echo "✓ Dell-Fleet-User created"
fi

echo ""
echo "============================================"
echo "Verifying credentials are accessible..."
echo "============================================"

# Test fetch via provision-listener
PROVISION_STATUS=$(curl -sf http://localhost:9999/credentials/status 2>/dev/null || echo '{"configured":false}')

if echo "$PROVISION_STATUS" | grep -q '"configured":true'; then
    echo "Testing credential fetch via provision-listener..."

    # Clear the cache by restarting provision-listener or waiting
    echo "(Note: Cache TTL is 5 minutes - new items may take a moment to appear)"

    ROOT_TEST=$(curl -sf http://localhost:9999/credentials/fleet-root/password 2>/dev/null || echo "")
    USER_TEST=$(curl -sf http://localhost:9999/credentials/fleet-user/password 2>/dev/null || echo "")

    if [ -n "$ROOT_TEST" ]; then
        echo "✓ fleet-root credential accessible via provision-listener"
    else
        echo "⚠ fleet-root not yet accessible (may need cache refresh)"
    fi

    if [ -n "$USER_TEST" ]; then
        echo "✓ fleet-user credential accessible via provision-listener"
    else
        echo "⚠ fleet-user not yet accessible (may need cache refresh)"
    fi
else
    echo "⚠ Provision-listener not configured for 1Password"
fi

echo ""
echo "============================================"
echo "Fleet credentials setup complete!"
echo "============================================"
echo ""
echo "The kickstart files will now be able to fetch"
echo "credentials from 1Password during PXE boot."
echo ""
echo "Next steps:"
echo "1. Verify credentials appear in 1Password app"
echo "2. Test: curl http://localhost:9999/credentials/fleet-root/password"
echo "3. Proceed with PXE boot testing"
