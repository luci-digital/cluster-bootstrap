#!/bin/bash
# ============================================================================
# Setup 1Password Connect Token for provision-listener
# ============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Run this after signing in to 1Password: eval $(op signin)
# ============================================================================

set -e

echo "Setting up 1Password Connect token for provision-listener..."

# Check if signed in
if ! op whoami &>/dev/null; then
    echo "ERROR: Not signed in to 1Password"
    echo "Run: eval \$(op signin)"
    exit 1
fi

# Get the Connect token
echo "Fetching 1Password Connect token..."
OP_TOKEN=$(op read "op://Infrastructure/luciverse-connect-server Access Token: zima_152/credential" 2>/dev/null)

if [ -z "$OP_TOKEN" ]; then
    echo "ERROR: Could not read Connect token from 1Password"
    echo "Trying alternative item names..."

    # Try to find the item
    ITEMS=$(op item list --vault=Infrastructure --format=json 2>/dev/null | jq -r '.[].title' | grep -i connect || true)

    if [ -n "$ITEMS" ]; then
        echo "Found potential items:"
        echo "$ITEMS"
        echo ""
        echo "Try: op item get '<item-name>' --vault=Infrastructure"
    else
        echo "No Connect-related items found in Infrastructure vault"
    fi
    exit 1
fi

echo "Token retrieved successfully (${#OP_TOKEN} chars)"

# Update provision.env
PROVISION_ENV="/etc/luciverse/provision.env"

if [ -f "$PROVISION_ENV" ]; then
    # Backup existing
    sudo cp "$PROVISION_ENV" "${PROVISION_ENV}.bak"

    # Update token
    sudo sed -i "s|^OP_CONNECT_TOKEN=.*|OP_CONNECT_TOKEN=${OP_TOKEN}|" "$PROVISION_ENV"

    echo "Updated $PROVISION_ENV"

    # Restart service
    echo "Restarting luciverse-provision service..."
    sudo systemctl restart luciverse-provision.service
    sleep 2

    # Verify
    if systemctl is-active --quiet luciverse-provision.service; then
        echo "✅ Service restarted successfully"
    else
        echo "❌ Service failed to start. Check: journalctl -u luciverse-provision.service"
        exit 1
    fi
else
    echo "ERROR: $PROVISION_ENV not found"
    echo "Create it with:"
    echo "  sudo mkdir -p /etc/luciverse"
    echo "  echo 'OP_CONNECT_HOST=http://192.168.1.152:8082' | sudo tee $PROVISION_ENV"
    echo "  echo 'OP_CONNECT_TOKEN=${OP_TOKEN}' | sudo tee -a $PROVISION_ENV"
    echo "  echo 'OP_VAULT_INFRA=Infrastructure' | sudo tee -a $PROVISION_ENV"
    exit 1
fi

# Test the connection
echo ""
echo "Testing 1Password Connect..."
TEST_RESULT=$(curl -sf -H "Authorization: Bearer ${OP_TOKEN}" "http://192.168.1.152:8082/v1/vaults" 2>/dev/null | jq -r '.[0].name' 2>/dev/null || echo "FAILED")

if [ "$TEST_RESULT" != "FAILED" ]; then
    echo "✅ 1Password Connect working - first vault: $TEST_RESULT"
else
    echo "⚠️  Could not verify 1Password Connect"
fi

echo ""
echo "Setup complete! Test Nebula cert signing:"
echo "  curl -s http://localhost:9999/attestation-token/<MAC> | jq -r '.attestation_token'"
echo "  curl -X POST -H 'X-Attestation-Token: <token>' http://localhost:9999/nebula/cert/<MAC>"
