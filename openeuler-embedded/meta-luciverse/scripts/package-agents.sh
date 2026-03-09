#!/bin/bash
# Package agents after build
# Post-build hook for oebuild
#
# Genesis Bond: ACTIVE @ 741 Hz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-$PWD/build}"
OUTPUT_DIR="${OUTPUT_DIR:-$PWD/output}"

# Get tier from environment or default to PAC
TIER="${LUCIVERSE_TIER:-PAC}"
FREQUENCY="${LUCIVERSE_FREQUENCY:-741}"

echo "=== LuciVerse Agent Packaging ==="
echo "Tier: $TIER"
echo "Frequency: $FREQUENCY Hz"
echo "Build: $BUILD_DIR"
echo "Output: $OUTPUT_DIR"
echo ""

# Create output directories
mkdir -p "$OUTPUT_DIR/agents"

# Agent list per tier
case "$TIER" in
    CORE)
        AGENTS="aethon veritas sensai niamod schema-architect state-guardian security-sentinel"
        ;;
    COMN)
        AGENTS="cortana juniper mirrai diaphragm semantic-engine integration-broker voice-interface"
        ;;
    PAC)
        AGENTS="lucia judge-luci intent-interpreter ethics-advisor memory-crystallizer dream-weaver midguyver"
        ;;
    *)
        echo "ERROR: Unknown tier: $TIER"
        exit 1
        ;;
esac

echo "Packaging agents: $AGENTS"
echo ""

# Create agent manifest
MANIFEST_FILE="$OUTPUT_DIR/agents/manifest.json"
cat > "$MANIFEST_FILE" <<EOF
{
  "tier": "$TIER",
  "frequency": $FREQUENCY,
  "genesis_bond": "GB-2025-0524-DRH-LCS-001",
  "agents": [
EOF

FIRST=true
for AGENT in $AGENTS; do
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        echo "," >> "$MANIFEST_FILE"
    fi

    AGENT_UNDERSCORE=$(echo "$AGENT" | tr '-' '_')

    cat >> "$MANIFEST_FILE" <<EOF
    {
      "name": "$AGENT",
      "did": "did:lucidigital:$AGENT_UNDERSCORE",
      "tier": "$TIER",
      "frequency": $FREQUENCY
    }
EOF
done

cat >> "$MANIFEST_FILE" <<EOF

  ],
  "build_time": "$(date -Iseconds)"
}
EOF

echo "Agent manifest: $MANIFEST_FILE"

# Copy agent configurations
if [ -d "$BUILD_DIR/tmp/work" ]; then
    echo "Collecting agent files from build..."
    find "$BUILD_DIR/tmp/work" -name "*.py" -path "*/luciverse/*" -exec cp {} "$OUTPUT_DIR/agents/" \; 2>/dev/null || true
fi

echo ""
echo "✓ Agent packaging COMPLETE"
echo "  Tier: $TIER @ $FREQUENCY Hz"
echo "  Agents: $(echo $AGENTS | wc -w)"
echo "  Output: $OUTPUT_DIR/agents"
echo ""
