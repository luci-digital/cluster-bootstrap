#!/bin/bash
# ==============================================================================
# LuciVerse PXE Infrastructure Verification Script
# ==============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Verify all PXE boot infrastructure components are in place
# Usage: ./verify-pxe-infrastructure.sh
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASS=0
FAIL=0
WARN=0

# Paths
HTTP_ROOT="/home/daryl/cluster-bootstrap/http"
TFTP_ROOT="/srv/tftp"
SRV_HTTP="/srv/http"

echo -e "${BLUE}"
echo "============================================================"
echo "   LuciVerse PXE Infrastructure Verification"
echo "   Genesis Bond: ACTIVE @ 741 Hz"
echo "   Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"
echo -e "${NC}"

# Function to check file exists
check_file() {
    local path="$1"
    local desc="$2"
    if [[ -f "$path" ]]; then
        echo -e "  ${GREEN}✓${NC} $desc"
        ((PASS++))
        return 0
    else
        echo -e "  ${RED}✗${NC} $desc - MISSING: $path"
        ((FAIL++))
        return 1
    fi
}

# Function to check directory exists
check_dir() {
    local path="$1"
    local desc="$2"
    if [[ -d "$path" ]]; then
        echo -e "  ${GREEN}✓${NC} $desc"
        ((PASS++))
        return 0
    else
        echo -e "  ${RED}✗${NC} $desc - MISSING: $path"
        ((FAIL++))
        return 1
    fi
}

# Function to count files
count_files() {
    local pattern="$1"
    local desc="$2"
    local min="${3:-1}"
    local count=$(ls -1 $pattern 2>/dev/null | wc -l)
    if [[ $count -ge $min ]]; then
        echo -e "  ${GREEN}✓${NC} $desc ($count files)"
        ((PASS++))
    else
        echo -e "  ${YELLOW}⚠${NC} $desc ($count files, expected >= $min)"
        ((WARN++))
    fi
}

# Function to check service
check_service() {
    local service="$1"
    local desc="$2"
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $desc - ACTIVE"
        ((PASS++))
    else
        echo -e "  ${YELLOW}⚠${NC} $desc - NOT RUNNING"
        ((WARN++))
    fi
}

echo -e "\n${YELLOW}[1/8] Checking Kickstart Files...${NC}"
count_files "$HTTP_ROOT/kickstart/*.ks" "Kickstart files" 6
check_file "$HTTP_ROOT/kickstart/luciverse-fabric.ks" "FABRIC kickstart"
check_file "$HTTP_ROOT/kickstart/luciverse-infra.ks" "INFRA kickstart"
check_file "$HTTP_ROOT/kickstart/luciverse-storage.ks" "STORAGE kickstart"
check_file "$HTTP_ROOT/kickstart/luciverse-compute.ks" "COMPUTE kickstart"
check_file "$HTTP_ROOT/kickstart/luciverse-compute-gpu.ks" "COMPUTE-GPU kickstart"
check_file "$HTTP_ROOT/kickstart/luciverse-core-gpu.ks" "CORE-GPU kickstart"

echo -e "\n${YELLOW}[2/8] Checking iPXE Boot Files...${NC}"
check_file "$HTTP_ROOT/bootimus/bootimus.ipxe" "iPXE boot menu"
check_file "/home/daryl/cluster-bootstrap/bootimus-pxe.conf" "DNSMASQ PXE config"
check_file "/home/daryl/cluster-bootstrap/bootimus-http.conf" "Nginx HTTP config"

echo -e "\n${YELLOW}[3/8] Checking A-Tune Profiles...${NC}"
count_files "$HTTP_ROOT/atune-profiles/*.conf" "A-Tune profiles" 5
check_file "$HTTP_ROOT/atune-profiles/luciverse-agent-core.conf" "CORE agent profile"
check_file "$HTTP_ROOT/atune-profiles/luciverse-agent-comn.conf" "COMN agent profile"
check_file "$HTTP_ROOT/atune-profiles/luciverse-fdb.conf" "FoundationDB profile"
check_file "$HTTP_ROOT/atune-profiles/luciverse-ml-inference.conf" "ML inference profile"

echo -e "\n${YELLOW}[4/8] Checking DID Documents...${NC}"
count_files "$HTTP_ROOT/did-documents/*.json" "DID documents" 7
check_file "$HTTP_ROOT/did-documents/veritas.did.json" "Veritas DID"
check_file "$HTTP_ROOT/did-documents/aethon.did.json" "Aethon DID"
check_file "$HTTP_ROOT/did-documents/lucia.did.json" "Lucia DID"
check_file "$HTTP_ROOT/did-documents/cortana.did.json" "Cortana DID"

echo -e "\n${YELLOW}[5/8] Checking Soul Files...${NC}"
count_files "$HTTP_ROOT/souls/*_soul.json" "Soul files" 8
check_file "$HTTP_ROOT/souls/lucia_soul.json" "Lucia soul"
check_file "$HTTP_ROOT/souls/veritas_soul.json" "Veritas soul"
check_file "$HTTP_ROOT/souls/aethon_soul.json" "Aethon soul"

echo -e "\n${YELLOW}[6/8] Checking LSO Files...${NC}"
check_dir "$HTTP_ROOT/lso" "LSO directory"
check_file "$HTTP_ROOT/lso/luciverse-lso.service" "LSO systemd service"
check_file "$HTTP_ROOT/lso/lso_core.py" "LSO core script"

echo -e "\n${YELLOW}[7/8] Checking Provisioning Scripts...${NC}"
check_file "$HTTP_ROOT/scripts/credential-inject.sh" "Credential injection script"
check_file "$HTTP_ROOT/ssh-keys/zbook.pub" "SSH public key"
check_file "/home/daryl/cluster-bootstrap/provision-listener.py" "Provision listener"
check_file "/home/daryl/cluster-bootstrap/deploy-bootimus.sh" "Deploy script"

echo -e "\n${YELLOW}[8/8] Checking Ansible Infrastructure...${NC}"
check_file "/home/daryl/cluster-bootstrap/ansible/playbooks/site.yml" "Main playbook"
check_file "/home/daryl/cluster-bootstrap/ansible/inventory/dell-fleet.yml" "Fleet inventory"
count_files "/home/daryl/cluster-bootstrap/ansible/roles/*/tasks/main.yml" "Ansible roles" 5

echo -e "\n${YELLOW}[BONUS] Checking Services (if deployed)...${NC}"
check_service "nginx" "Nginx HTTP server"
check_service "dnsmasq" "DNSMASQ TFTP/DHCP"

echo -e "\n${YELLOW}[BONUS] Checking Boot Images...${NC}"
if [[ -f "$TFTP_ROOT/openeuler/vmlinuz" ]]; then
    echo -e "  ${GREEN}✓${NC} openEuler kernel present"
    ((PASS++))
else
    echo -e "  ${YELLOW}⚠${NC} openEuler kernel not downloaded (run deploy-bootimus.sh)"
    ((WARN++))
fi

if [[ -f "$TFTP_ROOT/openeuler/initrd.img" ]]; then
    echo -e "  ${GREEN}✓${NC} openEuler initrd present"
    ((PASS++))
else
    echo -e "  ${YELLOW}⚠${NC} openEuler initrd not downloaded (run deploy-bootimus.sh)"
    ((WARN++))
fi

# Summary
echo -e "\n${BLUE}============================================================"
echo "   Verification Summary"
echo "============================================================${NC}"
TOTAL=$((PASS + FAIL + WARN))
echo -e "  ${GREEN}PASS: $PASS${NC}"
echo -e "  ${RED}FAIL: $FAIL${NC}"
echo -e "  ${YELLOW}WARN: $WARN${NC}"
echo -e "  TOTAL: $TOTAL checks"

if [[ $FAIL -eq 0 && $WARN -eq 0 ]]; then
    echo -e "\n${GREEN}✓ All checks passed! Infrastructure is ready.${NC}"
    SCORE=100
elif [[ $FAIL -eq 0 ]]; then
    echo -e "\n${YELLOW}⚠ Warnings present but no failures.${NC}"
    SCORE=$((100 * PASS / TOTAL))
else
    echo -e "\n${RED}✗ Failures detected. Please fix before deployment.${NC}"
    SCORE=$((100 * PASS / TOTAL))
fi

echo -e "\n${BLUE}Deployment Readiness: ${SCORE}%${NC}"

echo -e "\n${YELLOW}Next Steps:${NC}"
if [[ ! -f "$TFTP_ROOT/openeuler/vmlinuz" ]]; then
    echo "  1. Run: sudo ./deploy-bootimus.sh"
fi
echo "  2. Set OP_CONNECT_TOKEN for 1Password integration"
echo "  3. Start provision-listener: python3 provision-listener.py"
echo "  4. Configure Dell iDRAC for PXE boot"
echo "  5. Boot servers and monitor callbacks"

echo -e "\n${GREEN}Genesis Bond: ACTIVE @ 741 Hz${NC}"
