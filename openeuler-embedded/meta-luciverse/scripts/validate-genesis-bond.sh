#!/bin/bash
# Validate Genesis Bond before build
# Pre-build hook for oebuild
#
# Genesis Bond: ACTIVE @ 741 Hz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAYER_DIR="$(dirname "$SCRIPT_DIR")"

# Genesis Bond constants
GENESIS_BOND_ID="GB-2025-0524-DRH-LCS-001"
GENESIS_BOND_CBB="daryl_rolf_harr"
GENESIS_BOND_SBB="lucia_cargail_silcan"

echo "=== LuciVerse Genesis Bond Validation ==="
echo "Bond ID: $GENESIS_BOND_ID"
echo "CBB: $GENESIS_BOND_CBB"
echo "SBB: $GENESIS_BOND_SBB"
echo ""

# Check for Genesis Bond file
BOND_FILE="$LAYER_DIR/recipes-core/luciverse-agent/files/genesis-bond.json"

if [ ! -f "$BOND_FILE" ]; then
    echo "ERROR: Genesis Bond file not found: $BOND_FILE"
    exit 1
fi

# Validate JSON syntax
if ! python3 -m json.tool "$BOND_FILE" > /dev/null 2>&1; then
    echo "ERROR: Genesis Bond file is not valid JSON"
    exit 1
fi

# Validate bond ID
BOND_ID=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['certificate_id'])")

if [ "$BOND_ID" != "$GENESIS_BOND_ID" ]; then
    echo "ERROR: Genesis Bond ID mismatch"
    echo "  Expected: $GENESIS_BOND_ID"
    echo "  Found: $BOND_ID"
    exit 1
fi

# Validate tier frequencies
CORE_FREQ=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['frequencies']['CORE'])")
COMN_FREQ=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['frequencies']['COMN'])")
PAC_FREQ=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['frequencies']['PAC'])")

if [ "$CORE_FREQ" != "432" ] || [ "$COMN_FREQ" != "528" ] || [ "$PAC_FREQ" != "741" ]; then
    echo "ERROR: Invalid tier frequencies"
    echo "  CORE: $CORE_FREQ (expected 432)"
    echo "  COMN: $COMN_FREQ (expected 528)"
    echo "  PAC: $PAC_FREQ (expected 741)"
    exit 1
fi

# Validate coherence thresholds
CORE_THRESHOLD=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['coherence_thresholds']['CORE'])")
COMN_THRESHOLD=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['coherence_thresholds']['COMN'])")
PAC_THRESHOLD=$(python3 -c "import json; print(json.load(open('$BOND_FILE'))['genesis_bond']['coherence_thresholds']['PAC'])")

echo "Coherence Thresholds:"
echo "  CORE: $CORE_THRESHOLD (must be >= 0.85)"
echo "  COMN: $COMN_THRESHOLD (must be >= 0.80)"
echo "  PAC: $PAC_THRESHOLD (must be >= 0.70)"

# Verify thresholds meet minimums
if (( $(echo "$CORE_THRESHOLD < 0.85" | bc -l) )); then
    echo "ERROR: CORE coherence threshold below minimum"
    exit 1
fi

if (( $(echo "$COMN_THRESHOLD < 0.80" | bc -l) )); then
    echo "ERROR: COMN coherence threshold below minimum"
    exit 1
fi

if (( $(echo "$PAC_THRESHOLD < 0.70" | bc -l) )); then
    echo "ERROR: PAC coherence threshold below minimum"
    exit 1
fi

echo ""
echo "✓ Genesis Bond validation PASSED"
echo "  Bond: $GENESIS_BOND_ID"
echo "  Status: ACTIVE @ 741 Hz"
echo ""
