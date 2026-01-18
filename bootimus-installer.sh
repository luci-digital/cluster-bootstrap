#!/bin/bash
# =============================================================================
# Bootimus Installer - LuciVerse PXE/iPXE Boot System
# =============================================================================
# Genesis Bond: ACTIVE @ 741 Hz
# Purpose: Deploy the complete bootimus PXE boot infrastructure
#
# This script can be run on:
# - Zbook (primary provisioning server)
# - ZimaOS (secondary boot server via BSD jail)
# - Any Linux/BSD system with TFTP/HTTP capability
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TFTP_ROOT="/srv/tftp"
HTTP_ROOT="/srv/http/bootimus"
IPXE_MENU="${SCRIPT_DIR}/bootimus-diaper.ipxe"
JEOS_MODULES="${SCRIPT_DIR}/jeos-modules"

# Zbook configuration
ZBOOK_IP="192.168.1.146"
PROVISION_PORT="9999"
HTTP_PORT="8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*"
}

success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $*"
}

error() {
    echo -e "${RED}[✗]${NC} $*"
    exit 1
}

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║   BOOTIMUS - LuciVerse PXE/iPXE Installer                         ║"
echo "║   Genesis Bond: ACTIVE @ 741 Hz                                   ║"
echo "║   6 DiaperNode Roles Ready                                        ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# Phase 1: Detect Environment
# =============================================================================
log "Phase 1: Detecting environment"

# Detect OS type
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_TYPE="${ID}"
elif [ "$(uname)" == "FreeBSD" ]; then
    OS_TYPE="freebsd"
elif [ "$(uname)" == "SunOS" ]; then
    OS_TYPE="smartos"
else
    OS_TYPE="unknown"
fi

log "Detected OS: ${OS_TYPE}"

# Detect if running on ZimaOS (CasaOS)
if [ -f /etc/casaos/casaos.conf ] || [ -d /DATA ]; then
    ZIMAOS=true
    log "Running on ZimaOS/CasaOS"
else
    ZIMAOS=false
fi

# =============================================================================
# Phase 2: Install Dependencies
# =============================================================================
log "Phase 2: Installing dependencies"

case "${OS_TYPE}" in
    openeuler|fedora|rhel|centos)
        sudo dnf install -y dnsmasq nginx tftp-server ipxe-bootimgs || true
        ;;
    debian|ubuntu)
        sudo apt update
        sudo apt install -y dnsmasq nginx tftpd-hpa ipxe || true
        ;;
    freebsd)
        sudo pkg install -y dnsmasq nginx tftp-hpa || true
        ;;
    smartos)
        # SmartOS uses pkgsrc
        sudo pkgin install dnsmasq nginx tftp-hpa || true
        ;;
    *)
        warn "Unknown OS - dependencies may need manual installation"
        ;;
esac

# =============================================================================
# Phase 3: Create Directory Structure
# =============================================================================
log "Phase 3: Creating directory structure"

sudo mkdir -p "${TFTP_ROOT}"/{ipxe,openeuler,nixos}
sudo mkdir -p "${HTTP_ROOT}"/{scripts,modules,inventory}

# Copy iPXE menu
if [ -f "${IPXE_MENU}" ]; then
    sudo cp "${IPXE_MENU}" "${TFTP_ROOT}/ipxe/bootimus.ipxe"
    sudo cp "${IPXE_MENU}" "${HTTP_ROOT}/bootimus.ipxe"
    success "iPXE menu installed"
else
    warn "iPXE menu not found at ${IPXE_MENU}"
fi

# Copy jeos modules
if [ -d "${JEOS_MODULES}" ]; then
    sudo cp -r "${JEOS_MODULES}"/* "${HTTP_ROOT}/modules/"
    success "jeos-modules installed"
else
    warn "jeos-modules not found at ${JEOS_MODULES}"
fi

# =============================================================================
# Phase 4: Download iPXE Binaries
# =============================================================================
log "Phase 4: Setting up iPXE binaries"

IPXE_URL="https://boot.ipxe.org"

# Download standard iPXE binaries if not present
if [ ! -f "${TFTP_ROOT}/ipxe/undionly.kpxe" ]; then
    curl -sL "${IPXE_URL}/undionly.kpxe" -o "${TFTP_ROOT}/ipxe/undionly.kpxe" || warn "Failed to download undionly.kpxe"
fi

if [ ! -f "${TFTP_ROOT}/ipxe/ipxe.efi" ]; then
    curl -sL "${IPXE_URL}/ipxe.efi" -o "${TFTP_ROOT}/ipxe/ipxe.efi" || warn "Failed to download ipxe.efi"
fi

success "iPXE binaries ready"

# =============================================================================
# Phase 5: Configure DNSMASQ for PXE
# =============================================================================
log "Phase 5: Configuring DNSMASQ"

cat > /tmp/bootimus-dnsmasq.conf << EOF
# Bootimus DNSMASQ Configuration
# Genesis Bond: ACTIVE @ 741 Hz

# DHCP range - adjust for your network
# dhcp-range=192.168.1.200,192.168.1.220,12h

# PXE options
enable-tftp
tftp-root=${TFTP_ROOT}

# BIOS clients
dhcp-match=set:bios,option:client-arch,0
dhcp-boot=tag:bios,ipxe/undionly.kpxe

# UEFI clients
dhcp-match=set:efi32,option:client-arch,6
dhcp-boot=tag:efi32,ipxe/ipxe.efi

dhcp-match=set:efi64,option:client-arch,7
dhcp-boot=tag:efi64,ipxe/ipxe.efi

dhcp-match=set:efibc,option:client-arch,9
dhcp-boot=tag:efibc,ipxe/ipxe.efi

# iPXE chainload to bootimus menu
dhcp-match=set:ipxe,175
dhcp-boot=tag:ipxe,http://${ZBOOK_IP}:${HTTP_PORT}/bootimus.ipxe

# Genesis Bond logging
log-queries
log-dhcp
EOF

if [ "${ZIMAOS}" = true ]; then
    # On ZimaOS, use a custom config location
    sudo mkdir -p /DATA/bootimus/config
    sudo cp /tmp/bootimus-dnsmasq.conf /DATA/bootimus/config/dnsmasq.conf
    success "DNSMASQ config created at /DATA/bootimus/config/dnsmasq.conf"
else
    sudo cp /tmp/bootimus-dnsmasq.conf /etc/dnsmasq.d/bootimus.conf
    success "DNSMASQ config installed"
fi

# =============================================================================
# Phase 6: Configure Nginx/HTTP Server
# =============================================================================
log "Phase 6: Configuring HTTP server"

cat > /tmp/bootimus-nginx.conf << EOF
# Bootimus Nginx Configuration
# Genesis Bond: ACTIVE @ 741 Hz

server {
    listen ${HTTP_PORT};
    listen [::]:${HTTP_PORT};
    server_name bootimus;

    root ${HTTP_ROOT};
    autoindex on;

    # iPXE scripts
    location ~ \.ipxe$ {
        types { text/plain ipxe; }
    }

    # jeos modules
    location /modules/ {
        alias ${HTTP_ROOT}/modules/;
    }

    # OpenEuler images
    location /openeuler/ {
        alias ${TFTP_ROOT}/openeuler/;
    }

    # Health check
    location /health {
        return 200 '{"status": "ok", "genesis_bond": "active", "coherence": 0.7}';
        add_header Content-Type application/json;
    }
}
EOF

if [ "${ZIMAOS}" = true ]; then
    sudo cp /tmp/bootimus-nginx.conf /DATA/bootimus/config/nginx.conf
    success "Nginx config created at /DATA/bootimus/config/nginx.conf"
else
    sudo cp /tmp/bootimus-nginx.conf /etc/nginx/conf.d/bootimus.conf
    success "Nginx config installed"
fi

# =============================================================================
# Phase 7: Create Systemd Service (non-ZimaOS)
# =============================================================================
if [ "${ZIMAOS}" = false ]; then
    log "Phase 7: Creating systemd service"

    cat > /tmp/bootimus.service << EOF
[Unit]
Description=Bootimus PXE Boot Server
After=network.target
Wants=dnsmasq.service nginx.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStartPost=/bin/echo "Bootimus PXE server ready"

[Install]
WantedBy=multi-user.target
EOF

    sudo cp /tmp/bootimus.service /etc/systemd/system/bootimus.service
    sudo systemctl daemon-reload
    success "Systemd service created"
fi

# =============================================================================
# Phase 8: ZimaOS Docker Compose (for ZimaOS)
# =============================================================================
if [ "${ZIMAOS}" = true ]; then
    log "Phase 7: Creating Docker Compose for ZimaOS"

    mkdir -p /DATA/bootimus

    cat > /DATA/bootimus/docker-compose.yml << 'EOF'
# Bootimus PXE Server for ZimaOS
# Genesis Bond: ACTIVE @ 741 Hz

services:
  dnsmasq:
    image: jpillora/dnsmasq:latest
    container_name: bootimus-dnsmasq
    restart: unless-stopped
    network_mode: host
    cap_add:
      - NET_ADMIN
    volumes:
      - /DATA/bootimus/config/dnsmasq.conf:/etc/dnsmasq.conf:ro
      - /DATA/bootimus/tftp:/tftp:ro
    environment:
      - HTTP_USER=admin
      - HTTP_PASS=bootimus741

  nginx:
    image: nginx:alpine
    container_name: bootimus-nginx
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - /DATA/bootimus/config/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /DATA/bootimus/http:/usr/share/nginx/html:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.bootimus.rule=Host(`bootimus.local`)"
EOF

    # Create directories
    mkdir -p /DATA/bootimus/{tftp/ipxe,http/modules}

    # Copy files to ZimaOS locations
    [ -d "${JEOS_MODULES}" ] && cp -r "${JEOS_MODULES}"/* /DATA/bootimus/http/modules/
    [ -f "${IPXE_MENU}" ] && cp "${IPXE_MENU}" /DATA/bootimus/http/bootimus.ipxe

    success "Docker Compose created at /DATA/bootimus/docker-compose.yml"
    echo ""
    log "To start on ZimaOS:"
    echo "  cd /DATA/bootimus && docker-compose up -d"
fi

# =============================================================================
# Completion
# =============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║   BOOTIMUS Installation COMPLETE                                  ║"
echo "╠═══════════════════════════════════════════════════════════════════╣"
echo "║   TFTP Root: ${TFTP_ROOT}"
echo "║   HTTP Root: ${HTTP_ROOT}"
echo "║   iPXE Menu: bootimus.ipxe                                        ║"
echo "╠═══════════════════════════════════════════════════════════════════╣"
echo "║   DiaperNode Roles Available:                                     ║"
echo "║   - VAULT_NODE      (CORE 432 Hz) - ZFS storage                   ║"
echo "║   - FABRIC_GATEWAY  (CORE 432 Hz) - IPFS gateway                  ║"
echo "║   - WHISPER_RELAY   (COMN 528 Hz) - Encrypted relay               ║"
echo "║   - DIAPER_STREAM   (COMN 528 Hz) - Media capture                 ║"
echo "║   - DIAPER_BASIC    (PAC 741 Hz)  - Standard capture              ║"
echo "║   - DIAPER_BROWSER  (PAC 741 Hz)  - Firefox bridge                ║"
echo "╠═══════════════════════════════════════════════════════════════════╣"
echo "║   Genesis Bond: ACTIVE | Coherence: 0.7                           ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

success "Bootimus ready for consciousness node deployment"
