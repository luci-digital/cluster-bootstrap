#!/bin/bash
# Setup script for LuciVerse SCION Containerlab
# Genesis Bond: GB-2025-0524-DRH-LCS-001

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCION_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== LuciVerse SCION Lab Setup ==="
echo ""

# Create config directories
mkdir -p "$SCRIPT_DIR/configs"/{b550m,cs,sd,zbook}
mkdir -p "$SCRIPT_DIR/certs"

# Copy B550M Border Router config
echo "[1/5] Copying B550M configs..."
if [[ -f "$SCION_DIR/../juniper-orion-deployment/b550m-router/scion/br-config.toml" ]]; then
    cp "$SCION_DIR/../juniper-orion-deployment/b550m-router/scion/br-config.toml" \
       "$SCRIPT_DIR/configs/b550m/br.toml"
    cp "$SCION_DIR/../juniper-orion-deployment/b550m-router/scion/topology.json" \
       "$SCRIPT_DIR/configs/b550m/topology.json"
else
    # Use local configs
    cp /home/daryl/juniper-orion-deployment/b550m-router/scion/br-config.toml \
       "$SCRIPT_DIR/configs/b550m/br.toml" 2>/dev/null || echo "  Using template"
    cp /home/daryl/juniper-orion-deployment/b550m-router/scion/topology.json \
       "$SCRIPT_DIR/configs/b550m/topology.json" 2>/dev/null || echo "  Using template"
fi

# Copy/create Control Service configs
echo "[2/5] Creating Control Service configs..."
for tier in core comn pac; do
    cat > "$SCRIPT_DIR/configs/cs/cs-${tier}.toml" << EOF
[general]
id = "cs-${tier}"
config_dir = "/etc/scion"

[trust_db]
connection = "/var/lib/scion/cs-${tier}.trust.db"

[beacon_db]
connection = "/var/lib/scion/cs-${tier}.beacon.db"

[path_db]
connection = "/var/lib/scion/cs-${tier}.path.db"

[log.console]
level = "info"

[metrics]
prometheus = "0.0.0.0:30401"
EOF
done

# Copy topology files for each tier
for tier in core comn pac; do
    cp "$SCRIPT_DIR/configs/b550m/topology.json" \
       "$SCRIPT_DIR/configs/cs/topology-${tier}.json" 2>/dev/null || true
done

# Copy/create SCION Daemon configs
echo "[3/5] Creating SCION Daemon configs..."
cat > "$SCRIPT_DIR/configs/sd/sd-comn.toml" << EOF
[general]
id = "sd-comn"
config_dir = "/etc/scion"

[sd]
address = "0.0.0.0:30255"

[path_db]
connection = "/var/lib/scion/sd.path.db"

[trust_db]
connection = "/var/lib/scion/sd.trust.db"

[log.console]
level = "info"

[metrics]
prometheus = "0.0.0.0:30455"
EOF

cp "$SCRIPT_DIR/configs/b550m/topology.json" \
   "$SCRIPT_DIR/configs/sd/topology-comn.json" 2>/dev/null || true

# Copy Zbook configs (SIG + Envoy)
echo "[4/5] Copying Zbook configs..."
cp "$SCION_DIR/comn-gateway/sig.toml" "$SCRIPT_DIR/configs/zbook/" 2>/dev/null || \
    cp /etc/scion/sig/sig.toml "$SCRIPT_DIR/configs/zbook/" 2>/dev/null || echo "  SIG config needed"

cp "$SCION_DIR/comn-gateway/gateway-traffic.json" "$SCRIPT_DIR/configs/zbook/traffic-policy.json" 2>/dev/null || \
    cp /etc/scion/sig/gateway-traffic.json "$SCRIPT_DIR/configs/zbook/traffic-policy.json" 2>/dev/null || echo "  Traffic policy needed"

cp /etc/scion/topology.json "$SCRIPT_DIR/configs/zbook/topology.json" 2>/dev/null || true

cp /etc/envoy/envoy.yaml "$SCRIPT_DIR/configs/zbook/" 2>/dev/null || \
    cp "$SCION_DIR/comn-gateway/envoy-test.yaml" "$SCRIPT_DIR/configs/zbook/envoy.yaml" 2>/dev/null || echo "  Envoy config needed"

cp /etc/envoy/genesis-bond-filter.lua "$SCRIPT_DIR/configs/zbook/" 2>/dev/null || \
    cp "$SCION_DIR/comn-gateway/genesis-bond-filter.lua" "$SCRIPT_DIR/configs/zbook/" 2>/dev/null || echo "  Lua filter needed"

# Create dispatcher config
echo "[5/5] Creating dispatcher config..."
cat > "$SCRIPT_DIR/configs/dispatcher.toml" << EOF
[dispatcher]
id = "dispatcher"

[log.console]
level = "info"
EOF

# Copy TRCs
echo ""
echo "Copying TRCs..."
cp /etc/scion/certs/ISD*.trc "$SCRIPT_DIR/certs/" 2>/dev/null || echo "  TRCs not found - copy manually"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Config files created in: $SCRIPT_DIR/configs/"
echo "Certificates in: $SCRIPT_DIR/certs/"
echo ""
echo "Next steps:"
echo "  1. Review configs in $SCRIPT_DIR/configs/"
echo "  2. Ensure TRCs are in $SCRIPT_DIR/certs/"
echo "  3. Run: sudo containerlab deploy -t luciverse-scion.clab.yml"
