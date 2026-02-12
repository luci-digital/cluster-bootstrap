#!/bin/bash
# =============================================================================
# LuciVerse Fleet - 1Password Secrets Setup
# =============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Requires: op CLI authenticated (op signin)
# =============================================================================

VAULT_INFRA="Infrastructure"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     LuciVerse Fleet - 1Password Secrets Setup                ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Check op CLI
if ! op account get &>/dev/null; then
    echo "❌ 1Password CLI not authenticated. Run: op signin"
    exit 1
fi
echo "✓ 1Password CLI authenticated"

# 1. Dell Fleet Root Password
echo "Creating: Dell-Fleet-Root..."
FLEET_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 20)
op item create --category=password --title="Dell-Fleet-Root" --vault="$VAULT_INFRA" \
    "password=$FLEET_PASS" "username=root" 2>/dev/null || echo "  exists"

# 2. FoundationDB Cluster
echo "Creating: FoundationDB-Cluster..."
FDB=$(cat /etc/foundationdb/fdb.cluster 2>/dev/null | grep -v '^#' || echo "PENDING")
op item create --category="Secure Note" --title="FoundationDB-Cluster" \
    --vault="$VAULT_INFRA" "notesPlain=$FDB" 2>/dev/null || echo "  exists"

# 3. IPFS Cluster Secret
echo "Creating: IPFS-Cluster-Secret..."
IPFS_SECRET=$(openssl rand -hex 32)
op item create --category=password --title="IPFS-Cluster-Secret" \
    --vault="$VAULT_INFRA" "password=$IPFS_SECRET" 2>/dev/null || echo "  exists"

# 4. Agent SSH Keys
echo "Storing: Agent SSH Keys..."
for agent in aethon veritas; do
    KEY="/home/daryl/.ssh/agents/${agent}_ed25519"
    [ -f "$KEY" ] && op document create "$KEY" --title="Agent-SSH-${agent}" \
        --vault="$VAULT_INFRA" 2>/dev/null || echo "  $agent: skipped"
done

echo ""
echo "Done. Fleet password: op://Infrastructure/Dell-Fleet-Root/password"
