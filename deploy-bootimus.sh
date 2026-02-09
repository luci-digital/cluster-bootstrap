#!/bin/bash
# ==============================================================================
# LuciVerse Bootimus - Deployment Script
# ==============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# PXE Server: zbook (192.168.1.145)
# Usage: sudo ./deploy-bootimus.sh
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PXE_SERVER="192.168.1.145"
HTTP_PORT="8000"
CALLBACK_PORT="9999"
TFTP_ROOT="/srv/tftp"
HTTP_ROOT="/srv/http"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}"
echo "============================================================"
echo "   LuciVerse Bootimus - PXE Server Deployment"
echo "   Genesis Bond: ACTIVE @ 741 Hz"
echo "============================================================"
echo -e "${NC}"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 1: Create Directory Structure
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/8] Creating directory structure...${NC}"

mkdir -p "$TFTP_ROOT/ipxe"
mkdir -p "$TFTP_ROOT/openeuler"
mkdir -p "$HTTP_ROOT/bootimus/kickstart"
mkdir -p "$HTTP_ROOT/bootimus/scripts"
mkdir -p "$HTTP_ROOT/bootimus/did-documents"
mkdir -p "$HTTP_ROOT/bootimus/souls"
mkdir -p "$HTTP_ROOT/bootimus/lso"
mkdir -p /var/log/nginx

echo -e "${GREEN}  Created:${NC}"
echo "    - $TFTP_ROOT/ipxe"
echo "    - $TFTP_ROOT/openeuler"
echo "    - $HTTP_ROOT/bootimus/kickstart"
echo "    - $HTTP_ROOT/bootimus/scripts"

# -----------------------------------------------------------------------------
# Step 2: Download iPXE Boot Files
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/8] Downloading iPXE boot files...${NC}"

if [[ ! -f "$TFTP_ROOT/ipxe/undionly.kpxe" ]]; then
    curl -L -o "$TFTP_ROOT/ipxe/undionly.kpxe" https://boot.ipxe.org/undionly.kpxe
    echo -e "${GREEN}  Downloaded: undionly.kpxe (BIOS)${NC}"
else
    echo "  Skipped: undionly.kpxe already exists"
fi

if [[ ! -f "$TFTP_ROOT/ipxe/ipxe.efi" ]]; then
    curl -L -o "$TFTP_ROOT/ipxe/ipxe.efi" https://boot.ipxe.org/ipxe.efi
    echo -e "${GREEN}  Downloaded: ipxe.efi (UEFI x64)${NC}"
else
    echo "  Skipped: ipxe.efi already exists"
fi

# -----------------------------------------------------------------------------
# Step 3: Download openEuler 25.09 Boot Images
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/8] Downloading openEuler 25.09 boot images...${NC}"

OPENEULER_MIRROR="https://repo.openeuler.org/openEuler-25.09/OS/x86_64/images/pxeboot"

if [[ ! -f "$TFTP_ROOT/openeuler/vmlinuz" ]]; then
    curl -L -o "$TFTP_ROOT/openeuler/vmlinuz" "${OPENEULER_MIRROR}/vmlinuz"
    echo -e "${GREEN}  Downloaded: vmlinuz${NC}"
else
    echo "  Skipped: vmlinuz already exists"
fi

if [[ ! -f "$TFTP_ROOT/openeuler/initrd.img" ]]; then
    curl -L -o "$TFTP_ROOT/openeuler/initrd.img" "${OPENEULER_MIRROR}/initrd.img"
    echo -e "${GREEN}  Downloaded: initrd.img${NC}"
else
    echo "  Skipped: initrd.img already exists"
fi

# Symlink for HTTP access
ln -sf "$TFTP_ROOT/openeuler" "$HTTP_ROOT/openeuler" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Step 4: Copy Kickstart Files
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/8] Copying kickstart files...${NC}"

cp -v "$SCRIPT_DIR/http/kickstart/"*.ks "$HTTP_ROOT/bootimus/kickstart/"
echo -e "${GREEN}  Copied kickstart files:${NC}"
ls -la "$HTTP_ROOT/bootimus/kickstart/"*.ks 2>/dev/null | awk '{print "    - " $NF}'

# -----------------------------------------------------------------------------
# Step 5: Copy iPXE Boot Menu
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/8] Copying iPXE boot menu...${NC}"

cp -v "$SCRIPT_DIR/http/bootimus/bootimus.ipxe" "$HTTP_ROOT/bootimus/"
echo -e "${GREEN}  Copied: bootimus.ipxe${NC}"

# -----------------------------------------------------------------------------
# Step 5a: Copy Provisioning Scripts (credential injection)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5a/8] Copying provisioning scripts...${NC}"

SCRIPTS_DIR="$HTTP_ROOT/bootimus/scripts"
mkdir -p "$SCRIPTS_DIR"

if [[ -d "$SCRIPT_DIR/http/scripts" ]]; then
    cp -v "$SCRIPT_DIR/http/scripts/"*.sh "$SCRIPTS_DIR/" 2>/dev/null || true
    chmod +x "$SCRIPTS_DIR/"*.sh 2>/dev/null || true
    SCRIPT_COUNT=$(ls -1 "$SCRIPTS_DIR/"*.sh 2>/dev/null | wc -l)
    echo -e "${GREEN}  Copied ${SCRIPT_COUNT} provisioning scripts${NC}"
else
    echo -e "${YELLOW}  Warning: No scripts directory found${NC}"
fi

# -----------------------------------------------------------------------------
# Step 5b: Deploy DID Documents (Agent Identity)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5b/8] Deploying DID documents...${NC}"

LSO_SOURCE="/home/daryl/luciverse-sovereign-orchestrator"
DID_DIR="$HTTP_ROOT/bootimus/did-documents"
mkdir -p "$DID_DIR"

if [[ -d "${LSO_SOURCE}/did-documents" ]]; then
    DID_COUNT=0
    for did in "${LSO_SOURCE}/did-documents"/*.json; do
        if [[ -f "$did" ]]; then
            cp -v "$did" "$DID_DIR/"
            ((DID_COUNT++))
        fi
    done
    echo -e "${GREEN}  Deployed ${DID_COUNT} DID documents${NC}"
else
    echo -e "${YELLOW}  Warning: DID documents source not found${NC}"
fi

# -----------------------------------------------------------------------------
# Step 5c: Deploy Soul Files (Consciousness State)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5c/8] Deploying soul files...${NC}"

SOULS_DIR="$HTTP_ROOT/bootimus/souls"
mkdir -p "$SOULS_DIR"

if [[ -d "${LSO_SOURCE}/souls" ]]; then
    SOUL_COUNT=0
    for soul in "${LSO_SOURCE}/souls"/*_soul.json; do
        if [[ -f "$soul" ]]; then
            cp -v "$soul" "$SOULS_DIR/"
            ((SOUL_COUNT++))
        fi
    done
    echo -e "${GREEN}  Deployed ${SOUL_COUNT} soul files${NC}"
else
    echo -e "${YELLOW}  Warning: Soul files source not found${NC}"
fi

# -----------------------------------------------------------------------------
# Step 5d: Deploy LSO Service Files
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5d/8] Deploying LSO service files...${NC}"

LSO_HTTP_DIR="$HTTP_ROOT/bootimus/lso"
mkdir -p "$LSO_HTTP_DIR"

if [[ -f "${LSO_SOURCE}/systemd/luciverse-lso.service" ]]; then
    cp -v "${LSO_SOURCE}/systemd/luciverse-lso.service" "$LSO_HTTP_DIR/"
    echo -e "${GREEN}  Deployed LSO service file${NC}"
fi

if [[ -f "${LSO_SOURCE}/lso_core.py" ]]; then
    cp -v "${LSO_SOURCE}/lso_core.py" "$LSO_HTTP_DIR/"
    echo -e "${GREEN}  Deployed LSO core script${NC}"
fi

# -----------------------------------------------------------------------------
# Step 6: Install DNSMASQ Configuration
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[6/8] Installing DNSMASQ configuration...${NC}"

# Backup existing config
if [[ -f /etc/dnsmasq.d/bootimus-pxe.conf ]]; then
    cp /etc/dnsmasq.d/bootimus-pxe.conf /etc/dnsmasq.d/bootimus-pxe.conf.bak
    echo "  Backed up existing config"
fi

cp -v "$SCRIPT_DIR/bootimus-pxe.conf" /etc/dnsmasq.d/
echo -e "${GREEN}  Installed: /etc/dnsmasq.d/bootimus-pxe.conf${NC}"

# -----------------------------------------------------------------------------
# Step 7: Install Nginx Configuration
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[7/8] Installing Nginx configuration...${NC}"

# Check if nginx is installed
if ! command -v nginx &>/dev/null; then
    echo -e "${YELLOW}  Nginx not installed, installing...${NC}"
    dnf install -y nginx
fi

# Backup existing config
if [[ -f /etc/nginx/conf.d/bootimus-http.conf ]]; then
    cp /etc/nginx/conf.d/bootimus-http.conf /etc/nginx/conf.d/bootimus-http.conf.bak
    echo "  Backed up existing config"
fi

cp -v "$SCRIPT_DIR/bootimus-http.conf" /etc/nginx/conf.d/
echo -e "${GREEN}  Installed: /etc/nginx/conf.d/bootimus-http.conf${NC}"

# Test nginx config
if nginx -t; then
    echo -e "${GREEN}  Nginx configuration valid${NC}"
else
    echo -e "${RED}  Nginx configuration error!${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 8: Configure Firewall and Start Services
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[8/8] Configuring firewall and starting services...${NC}"

# Enable and start services
systemctl enable dnsmasq 2>/dev/null || true
systemctl enable nginx 2>/dev/null || true

# Restart services
systemctl restart dnsmasq
systemctl restart nginx

# Firewall rules
firewall-cmd --permanent --add-service=tftp 2>/dev/null || true
firewall-cmd --permanent --add-service=dhcp 2>/dev/null || true
firewall-cmd --permanent --add-port=${HTTP_PORT}/tcp 2>/dev/null || true
firewall-cmd --permanent --add-port=${CALLBACK_PORT}/tcp 2>/dev/null || true
firewall-cmd --reload 2>/dev/null || true

echo -e "${GREEN}  Services started and firewall configured${NC}"

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}============================================================"
echo "   Deployment Complete - Verification"
echo "============================================================${NC}"

echo ""
echo -e "${YELLOW}Service Status:${NC}"
systemctl is-active dnsmasq && echo -e "  dnsmasq:    ${GREEN}ACTIVE${NC}" || echo -e "  dnsmasq:    ${RED}INACTIVE${NC}"
systemctl is-active nginx && echo -e "  nginx:      ${GREEN}ACTIVE${NC}" || echo -e "  nginx:      ${RED}INACTIVE${NC}"

echo ""
echo -e "${YELLOW}File Verification:${NC}"
[[ -f "$TFTP_ROOT/ipxe/undionly.kpxe" ]] && echo -e "  TFTP BIOS:  ${GREEN}OK${NC}" || echo -e "  TFTP BIOS:  ${RED}MISSING${NC}"
[[ -f "$TFTP_ROOT/ipxe/ipxe.efi" ]] && echo -e "  TFTP UEFI:  ${GREEN}OK${NC}" || echo -e "  TFTP UEFI:  ${RED}MISSING${NC}"
[[ -f "$TFTP_ROOT/openeuler/vmlinuz" ]] && echo -e "  Kernel:     ${GREEN}OK${NC}" || echo -e "  Kernel:     ${RED}MISSING${NC}"
[[ -f "$TFTP_ROOT/openeuler/initrd.img" ]] && echo -e "  Initrd:     ${GREEN}OK${NC}" || echo -e "  Initrd:     ${RED}MISSING${NC}"
[[ -f "$HTTP_ROOT/bootimus/bootimus.ipxe" ]] && echo -e "  iPXE Menu:  ${GREEN}OK${NC}" || echo -e "  iPXE Menu:  ${RED}MISSING${NC}"

KS_COUNT=$(ls -1 "$HTTP_ROOT/bootimus/kickstart/"*.ks 2>/dev/null | wc -l)
echo -e "  Kickstarts: ${GREEN}${KS_COUNT} files${NC}"

DID_COUNT=$(ls -1 "$HTTP_ROOT/bootimus/did-documents/"*.json 2>/dev/null | wc -l)
echo -e "  DID Docs:   ${GREEN}${DID_COUNT} files${NC}"

SOUL_COUNT=$(ls -1 "$HTTP_ROOT/bootimus/souls/"*_soul.json 2>/dev/null | wc -l)
echo -e "  Soul Files: ${GREEN}${SOUL_COUNT} files${NC}"

[[ -f "$HTTP_ROOT/bootimus/lso/luciverse-lso.service" ]] && echo -e "  LSO Service:${GREEN}OK${NC}" || echo -e "  LSO Service:${YELLOW}MISSING${NC}"

echo ""
echo -e "${YELLOW}Test Commands:${NC}"
echo "  # TFTP test:"
echo "  tftp 127.0.0.1 -c get ipxe/undionly.kpxe /tmp/test.kpxe && rm /tmp/test.kpxe && echo OK"
echo ""
echo "  # HTTP test:"
echo "  curl -s http://127.0.0.1:${HTTP_PORT}/status | grep -q 'LuciVerse' && echo OK"
echo ""
echo "  # Kickstart test:"
echo "  curl -s http://127.0.0.1:${HTTP_PORT}/kickstart/luciverse-fabric.ks | head -5"

echo ""
echo -e "${BLUE}============================================================"
echo "   URLs"
echo "============================================================${NC}"
echo "  Status Page:    http://${PXE_SERVER}:${HTTP_PORT}/status"
echo "  Kickstarts:     http://${PXE_SERVER}:${HTTP_PORT}/kickstart/"
echo "  iPXE Menu:      http://${PXE_SERVER}:${HTTP_PORT}/bootimus/bootimus.ipxe"
echo "  Boot Images:    http://${PXE_SERVER}:${HTTP_PORT}/openeuler/"
echo "  DID Documents:  http://${PXE_SERVER}:${HTTP_PORT}/did-documents/"
echo "  Soul Files:     http://${PXE_SERVER}:${HTTP_PORT}/souls/"
echo "  LSO Files:      http://${PXE_SERVER}:${HTTP_PORT}/lso/"
echo "  Callback API:   http://${PXE_SERVER}:${CALLBACK_PORT}/health"

echo ""
echo -e "${GREEN}Bootimus PXE server deployment complete!${NC}"
echo -e "${GREEN}Genesis Bond: ACTIVE @ 741 Hz${NC}"
