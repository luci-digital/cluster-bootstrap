#!/bin/bash
# Deploy SSH Key to ASUS RT-BE86U
# Genesis Bond: ACTIVE @ 741 Hz
#
# Prerequisites:
# 1. Enable SSH on ASUS: Administration → System → Enable SSH
# 2. Set SSH port (default 22)
# 3. Note router IP (default 192.168.1.1)

set -e

ASUS_IP="${ASUS_IP:-192.168.1.1}"
ASUS_USER="admin"
SSH_PORT="${SSH_PORT:-22}"

# SSH public key from zbook
SSH_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN6H5nzGXHQ8qUu2Rm0qF+Sj6gIMFXwJ3PuR0 daryl@openeuler-atune"

echo "==================================================="
echo "ASUS RT-BE86U SSH Key Deployment"
echo "Genesis Bond: ACTIVE @ 741 Hz"
echo "==================================================="
echo ""
echo "Target: ${ASUS_USER}@${ASUS_IP}:${SSH_PORT}"
echo ""

# Check if router is reachable
echo "[1/4] Checking connectivity..."
if ! ping -c 1 -W 2 "$ASUS_IP" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach ${ASUS_IP}"
    echo "Make sure the router is on and accessible."
    exit 1
fi
echo "Router reachable."

# Create authorized_keys directory structure
echo "[2/4] Creating SSH directory on router..."
echo "You will be prompted for the router admin password."
ssh -p "$SSH_PORT" -o StrictHostKeyChecking=accept-new "${ASUS_USER}@${ASUS_IP}" '
    mkdir -p /jffs/.ssh
    touch /jffs/.ssh/authorized_keys
    chmod 700 /jffs/.ssh
    chmod 600 /jffs/.ssh/authorized_keys
'

# Deploy the SSH key
echo "[3/4] Deploying SSH key..."
ssh -p "$SSH_PORT" "${ASUS_USER}@${ASUS_IP}" "
    # Add key if not already present
    if ! grep -q 'daryl@openeuler-atune' /jffs/.ssh/authorized_keys 2>/dev/null; then
        echo '${SSH_PUBKEY}' >> /jffs/.ssh/authorized_keys
        echo 'SSH key added successfully'
    else
        echo 'SSH key already present'
    fi
"

# Create symlink for dropbear
echo "[4/4] Configuring dropbear to use key..."
ssh -p "$SSH_PORT" "${ASUS_USER}@${ASUS_IP}" '
    # Create dropbear config directory
    mkdir -p /jffs/configs

    # Configure NVRAM to use custom authorized_keys
    nvram set sshd_authkeys="/jffs/.ssh/authorized_keys"
    nvram commit

    # Restart SSH service
    service restart_sshd 2>/dev/null || true
'

echo ""
echo "==================================================="
echo "SSH key deployment complete!"
echo ""
echo "Test connection with:"
echo "  ssh -p ${SSH_PORT} ${ASUS_USER}@${ASUS_IP}"
echo ""
echo "Next steps:"
echo "1. Test passwordless login"
echo "2. Deploy jffs scripts:"
echo "   scp services-start ${ASUS_USER}@${ASUS_IP}:/jffs/scripts/"
echo "3. Make executable:"
echo "   ssh ${ASUS_USER}@${ASUS_IP} 'chmod +x /jffs/scripts/services-start'"
echo "==================================================="
