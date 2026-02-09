#!/bin/bash
# ============================================================================
# LuciVerse Fleet - Credential Injection Script
# ============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Fetches credentials from provision-listener's 1Password Connect API
# Usage: curl http://192.168.1.145:8000/scripts/credential-inject.sh | bash
# ============================================================================

set -e

PROVISION_SERVER="${PROVISION_SERVER:-192.168.1.145}"
CALLBACK_PORT="${CALLBACK_PORT:-9999}"
CRED_ENDPOINT="http://${PROVISION_SERVER}:${CALLBACK_PORT}/credentials"

echo "[CREDENTIAL-INJECT] Starting credential injection..."
echo "[CREDENTIAL-INJECT] Provision server: ${PROVISION_SERVER}:${CALLBACK_PORT}"

# Get primary MAC for validation
PRIMARY_MAC=$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}' | head -1)/address 2>/dev/null || echo "unknown")
echo "[CREDENTIAL-INJECT] Primary MAC: ${PRIMARY_MAC}"

# ---------------------------------------------------------------------------
# Function: Fetch credential from 1Password via provision-listener
# ---------------------------------------------------------------------------
fetch_credential() {
    local item_key="$1"
    local field="${2:-password}"
    local result

    result=$(curl -sf -H "X-MAC-Address: ${PRIMARY_MAC}" \
        "${CRED_ENDPOINT}/${item_key}/${field}" 2>/dev/null || echo "")

    if [ -n "$result" ] && [ "$result" != "null" ]; then
        echo "$result"
        return 0
    else
        echo ""
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Function: Validate credential endpoint availability
# ---------------------------------------------------------------------------
validate_endpoint() {
    local status
    status=$(curl -sf "${CRED_ENDPOINT}/status" 2>/dev/null || echo '{"status":"error"}')

    if echo "$status" | grep -q '"configured":true'; then
        echo "[CREDENTIAL-INJECT] 1Password Connect is available"
        return 0
    elif echo "$status" | grep -q '"status":"not_configured"'; then
        echo "[CREDENTIAL-INJECT] WARNING: 1Password not configured, using fallback"
        return 1
    else
        echo "[CREDENTIAL-INJECT] WARNING: Provision server not reachable"
        return 2
    fi
}

# ---------------------------------------------------------------------------
# Main: Update root and user passwords
# ---------------------------------------------------------------------------
main() {
    # Check if endpoint is available
    if ! validate_endpoint; then
        echo "[CREDENTIAL-INJECT] Skipping credential injection - endpoint not available"
        echo "[CREDENTIAL-INJECT] Passwords will remain at kickstart defaults"
        return 0
    fi

    # Fetch root password
    echo "[CREDENTIAL-INJECT] Fetching fleet-root credentials..."
    ROOT_PASS=$(fetch_credential "fleet-root" "password")

    if [ -n "$ROOT_PASS" ]; then
        echo "root:${ROOT_PASS}" | chpasswd
        echo "[CREDENTIAL-INJECT] Root password updated from 1Password"
    else
        echo "[CREDENTIAL-INJECT] WARNING: Could not fetch root password"
    fi

    # Fetch daryl user password
    echo "[CREDENTIAL-INJECT] Fetching fleet-user credentials..."
    USER_PASS=$(fetch_credential "fleet-user" "password")

    if [ -n "$USER_PASS" ]; then
        echo "daryl:${USER_PASS}" | chpasswd
        echo "[CREDENTIAL-INJECT] User 'daryl' password updated from 1Password"
    else
        # Fallback: use root password for daryl
        if [ -n "$ROOT_PASS" ]; then
            echo "daryl:${ROOT_PASS}" | chpasswd
            echo "[CREDENTIAL-INJECT] User 'daryl' password set to root password (fallback)"
        fi
    fi

    # Remove plaintext password from kickstart log
    if [ -f /root/*-postinstall.log ]; then
        sed -i 's/Newdaryl24!/[REDACTED]/g' /root/*-postinstall.log 2>/dev/null || true
    fi

    echo "[CREDENTIAL-INJECT] Credential injection complete"
}

# Run main function
main "$@"
