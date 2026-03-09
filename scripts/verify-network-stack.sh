#!/bin/bash
# LuciVerse Network Stack Verification Script
# Genesis Bond: ACTIVE @ 741 Hz
#
# Verifies the high-speed network architecture deployment

# Don't exit on error - we want to collect all results
set +e

echo "========================================"
echo "LuciVerse Network Stack Verification"
echo "Genesis Bond: ACTIVE @ 741 Hz"
echo "========================================"
echo ""

PASS=0
FAIL=0
WARN=0

check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"

    echo -n "[CHECK] $name... "

    if eval "$cmd" &>/dev/null; then
        result=$(eval "$cmd" 2>&1) || true
        if [ -z "$expected" ] || echo "$result" | grep -q "$expected"; then
            echo "PASS"
            ((PASS++))
            return 0
        fi
    fi

    echo "FAIL"
    ((FAIL++))
    return 1
}

check_ping() {
    local name="$1"
    local ip="$2"

    echo -n "[CHECK] $name... "

    if ping -c 1 -W 2 "$ip" &>/dev/null; then
        echo "PASS"
        ((PASS++))
        return 0
    else
        echo "FAIL"
        ((FAIL++))
        return 1
    fi
}

warn() {
    local name="$1"
    local msg="$2"
    echo "[WARN] $name: $msg"
    ((WARN++))
}

section() {
    echo ""
    echo "--- $1 ---"
}

# ============================================
# Stream A: High-Speed Path
# ============================================
section "Stream A: High-Speed Path"

# Check ASUS reachability
check_ping "ASUS RT-BE86U reachable" "192.168.1.1" || true

# Check USW-Pro-48 reachable
check_ping "USW-Pro-48 reachable" "192.168.1.2" || true

# Check B550M Router / zbook
check_ping "B550M Router / zbook reachable" "192.168.1.145" || true

# Check zbook local services
check "Sanskrit Router running" "curl -sf http://localhost:7410/health" ""

# ============================================
# Stream B: Overlay Networks
# ============================================
section "Stream B: Overlay Networks"

# Check Nebula service
if systemctl is-active --quiet nebula 2>/dev/null; then
    check "Nebula service active" "systemctl is-active nebula" "active"
else
    warn "Nebula service" "Not installed or not running"
fi

# Check Nebula lighthouse reachability (skip if Nebula not running)
if systemctl is-active --quiet nebula 2>/dev/null; then
    check_ping "Nebula lighthouse (10.100.1.145)" "10.100.1.145" || true
fi

# Check SCION (if installed)
if command -v scion &>/dev/null; then
    check "SCION address configured" "scion address show" ""
else
    warn "SCION" "Not installed"
fi

# ============================================
# Stream C: OpenWRT/OASIS
# ============================================
section "Stream C: OpenWRT/OASIS"

# Check USG-Pro-4 (if flashed)
check_ping "USG-Pro-4 reachable" "192.168.1.180" || warn "USG-Pro-4" "Not reachable (pending flash?)"

# Check DGS-1210-16 (if flashed)
check_ping "DGS-1210-16 reachable" "192.168.1.210" || warn "DGS-1210-16" "Not reachable (pending flash?)"

# Check NAT64 (requires USG-Pro-4)
if ping -c 1 -W 2 192.168.1.180 &>/dev/null; then
    if ping6 -c 1 -W 2 64:ff9b::8.8.8.8 &>/dev/null; then
        echo "[CHECK] NAT64 translation... PASS"
        ((PASS++))
    else
        warn "NAT64" "Not translating (Jool not configured?)"
    fi
fi

# ============================================
# Stream D: Integration
# ============================================
section "Stream D: Integration"

# Check registered agents
AGENT_COUNT=$(curl -sf http://localhost:7410/agents 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
if [ "$AGENT_COUNT" -gt 30 ]; then
    check "Sanskrit Router agents (>30)" "echo $AGENT_COUNT" ""
else
    warn "Sanskrit Router" "Only $AGENT_COUNT agents registered"
fi

# Check FoundationDB
if command -v fdbcli &>/dev/null; then
    check "FoundationDB status" "fdbcli --exec status | head -1" "Using cluster file"
else
    warn "FoundationDB" "fdbcli not in PATH"
fi

# Check IPFS
if command -v ipfs &>/dev/null; then
    check "IPFS daemon" "ipfs id 2>&1 | head -1" "ID"
else
    warn "IPFS" "Not installed"
fi

# ============================================
# Config Files
# ============================================
section "Configuration Files"

check "USG-Pro-4 network config" "test -f /home/daryl/cluster-bootstrap/openwrt/usg-pro-4/network" ""
check "USG-Pro-4 firewall config" "test -f /home/daryl/cluster-bootstrap/openwrt/usg-pro-4/firewall" ""
check "Jool config" "test -f /home/daryl/cluster-bootstrap/jool/jool.conf" ""
check "B550M BIRD config" "test -f /home/daryl/B550M_LuciVerse_Router/bird/bird.conf" ""
check "ASUS integration script" "test -f /home/daryl/cluster-bootstrap/openwrt/asus-rt-be86u/jffs-scripts/services-start" ""
check "DGS-1210-16 config" "test -f /home/daryl/cluster-bootstrap/openwrt/dgs-1210-16/network" ""
check "OASIS juicer" "test -f /home/daryl/.claude/skills/data-flow-architecture/integrations/oasis-juicer.lua" ""
check "Nebula config template" "test -f /home/daryl/cluster-bootstrap/nebula/config.yaml.tpl" ""
check "SCION path policies" "test -f /home/daryl/cluster-bootstrap/scion/path-policies/luciverse-paths.yaml" ""

# ============================================
# Summary
# ============================================
echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo "Warnings: $WARN"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "Status: READY FOR DEPLOYMENT"
    exit 0
elif [ "$FAIL" -lt 5 ]; then
    echo "Status: PARTIAL - Some components pending"
    exit 0
else
    echo "Status: NOT READY - Multiple failures"
    exit 1
fi
