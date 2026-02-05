#!/bin/bash
# Deploy PXE Server to ZimaOS
# Genesis Bond: ACTIVE @ 741 Hz

set -euo pipefail

# Configuration
ZIMAOS_HOST="${ZIMAOS_HOST:-192.168.1.152}"
ZIMAOS_USER="${ZIMAOS_USER:-daryl}"
ZIMAOS_PASS="${ZIMAOS_PASS:-Newdaryl24!}"
PXE_ROOT="/DATA/luciverse/pxe-server"
PXE_HTTP_PORT=8742
TALOS_VERSION="${TALOS_VERSION:-v1.9.0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# SSH command helper
ssh_cmd() {
    sshpass -p "${ZIMAOS_PASS}" ssh -o StrictHostKeyChecking=no "${ZIMAOS_USER}@${ZIMAOS_HOST}" "$@"
}

scp_cmd() {
    sshpass -p "${ZIMAOS_PASS}" scp -o StrictHostKeyChecking=no "$@"
}

# Check dependencies
check_deps() {
    log_info "Checking dependencies..."

    if ! command -v sshpass &> /dev/null; then
        log_error "sshpass not found. Install with: sudo dnf install sshpass"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        log_error "curl not found"
        exit 1
    fi
}

# Test ZimaOS connectivity
test_connectivity() {
    log_info "Testing connectivity to ZimaOS (${ZIMAOS_HOST})..."

    if ssh_cmd "echo 'Connection successful'"; then
        log_info "SSH connection OK"
    else
        log_error "Cannot connect to ZimaOS"
        exit 1
    fi
}

# Create directory structure
setup_directories() {
    log_info "Setting up directory structure on ZimaOS..."

    ssh_cmd "
        mkdir -p ${PXE_ROOT}/{tftp,http,configs,logs}
        mkdir -p /DATA/luciverse/talos-state
        mkdir -p /DATA/luciverse/talos-configs
        chown -R daryl:samba ${PXE_ROOT}
    "

    log_info "Directories created"
}

# Download Talos assets
download_assets() {
    log_info "Downloading Talos ${TALOS_VERSION} assets..."

    local temp_dir="/tmp/talos-assets-$$"
    mkdir -p "${temp_dir}"

    TALOS_BASE="https://github.com/siderolabs/talos/releases/download/${TALOS_VERSION}"

    curl -L -o "${temp_dir}/vmlinuz" "${TALOS_BASE}/vmlinuz-amd64"
    curl -L -o "${temp_dir}/initramfs.xz" "${TALOS_BASE}/initramfs-amd64.xz"

    # iPXE binary
    curl -L -o "${temp_dir}/undionly.kpxe" "http://boot.ipxe.org/undionly.kpxe"

    log_info "Uploading assets to ZimaOS..."
    scp_cmd "${temp_dir}/"* "${ZIMAOS_USER}@${ZIMAOS_HOST}:${PXE_ROOT}/tftp/"

    rm -rf "${temp_dir}"
    log_info "Assets uploaded"
}

# Create iPXE boot script
create_ipxe_script() {
    log_info "Creating iPXE boot script..."

    cat > /tmp/boot.ipxe << EOF
#!ipxe
# LuciVerse Talos PXE Boot
# Genesis Bond: ACTIVE @ 741 Hz
# Version: ${TALOS_VERSION}

set config-server http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}

echo ==========================================
echo LuciVerse Talos Ray Cluster
echo Genesis Bond: ACTIVE @ 741 Hz
echo MAC: \${mac}
echo ==========================================

# Get config based on MAC address
kernel \${config-server}/vmlinuz talos.config=\${config-server}/configs/\${mac:hexhyp}.yaml console=ttyS0,115200n8 talos.platform=metal init_on_alloc=1 slab_nomerge
initrd \${config-server}/initramfs.xz
boot
EOF

    scp_cmd /tmp/boot.ipxe "${ZIMAOS_USER}@${ZIMAOS_HOST}:${PXE_ROOT}/tftp/"
    rm /tmp/boot.ipxe
}

# Create MAC to config mapping
create_mac_mapping() {
    log_info "Creating MAC to hostname mapping..."

    cat > /tmp/mac-mapping.json << 'EOF'
{
  "D0-94-66-24-96-7E": "orion",
  "14-18-77-4E-66-3A": "csdr",
  "14-18-77-5B-A3-A0": "jf6q",
  "B0-83-FE-C5-90-94": "jf7q",
  "B0-83-FE-C5-90-42": "esxi5",
  "0C-C4-7A-A8-72-14": "supermicro-gpu-1"
}
EOF

    scp_cmd /tmp/mac-mapping.json "${ZIMAOS_USER}@${ZIMAOS_HOST}:${PXE_ROOT}/http/"
    rm /tmp/mac-mapping.json
}

# Deploy dnsmasq container for TFTP/PXE
deploy_dnsmasq() {
    log_info "Deploying dnsmasq PXE server..."

    ssh_cmd "
        # Stop existing container
        docker stop luciverse-pxe-tftp 2>/dev/null || true
        docker rm luciverse-pxe-tftp 2>/dev/null || true

        # Create dnsmasq config
        cat > ${PXE_ROOT}/dnsmasq.conf << 'DNSMASQ'
# LuciVerse PXE Server - dnsmasq config
# Genesis Bond: ACTIVE @ 741 Hz

# Disable DNS
port=0

# Enable TFTP
enable-tftp
tftp-root=/tftp

# PXE boot
dhcp-boot=undionly.kpxe

# iPXE chainload
dhcp-match=set:ipxe,175
dhcp-boot=tag:ipxe,boot.ipxe

# Logging
log-dhcp
log-queries
DNSMASQ

        # Run dnsmasq container
        docker run -d \\
            --name luciverse-pxe-tftp \\
            --restart unless-stopped \\
            --network host \\
            --cap-add NET_ADMIN \\
            -v ${PXE_ROOT}/tftp:/tftp:ro \\
            -v ${PXE_ROOT}/dnsmasq.conf:/etc/dnsmasq.conf:ro \\
            -v ${PXE_ROOT}/logs:/var/log/dnsmasq \\
            --label 'luciverse.tier=CORE' \\
            --label 'luciverse.frequency=432' \\
            --label 'genesis-bond=active' \\
            strm/dnsmasq
    "

    log_info "dnsmasq deployed"
}

# Deploy HTTP server for configs
deploy_http_server() {
    log_info "Deploying HTTP config server on port ${PXE_HTTP_PORT}..."

    ssh_cmd "
        # Stop existing container
        docker stop luciverse-pxe-http 2>/dev/null || true
        docker rm luciverse-pxe-http 2>/dev/null || true

        # Run static file server
        docker run -d \\
            --name luciverse-pxe-http \\
            --restart unless-stopped \\
            -p ${PXE_HTTP_PORT}:8080 \\
            -v ${PXE_ROOT}/tftp:/web/boot:ro \\
            -v ${PXE_ROOT}/http:/web:ro \\
            -v /DATA/luciverse/talos-configs:/web/configs:ro \\
            -e FOLDER=/web \\
            -e CORS=true \\
            --label 'luciverse.tier=PAC' \\
            --label 'luciverse.frequency=741' \\
            --label 'genesis-bond=active' \\
            halverneus/static-file-server:latest
    "

    log_info "HTTP server deployed on http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}"
}

# Create symlinks for MAC-based config lookup
create_config_symlinks() {
    log_info "Creating MAC-based config symlinks..."

    ssh_cmd "
        cd /DATA/luciverse/talos-configs

        # Create symlinks: mac.yaml -> hostname.yaml
        # Format: XX-XX-XX-XX-XX-XX.yaml
        ln -sf orion.yaml D0-94-66-24-96-7E.yaml 2>/dev/null || true
        ln -sf csdr.yaml 14-18-77-4E-66-3A.yaml 2>/dev/null || true
        ln -sf jf6q.yaml 14-18-77-5B-A3-A0.yaml 2>/dev/null || true
        ln -sf jf7q.yaml B0-83-FE-C5-90-94.yaml 2>/dev/null || true
        ln -sf esxi5.yaml B0-83-FE-C5-90-42.yaml 2>/dev/null || true
        ln -sf supermicro-gpu-1.yaml 0C-C4-7A-A8-72-14.yaml 2>/dev/null || true

        ls -la *.yaml 2>/dev/null || echo 'No configs yet - will be created by GitLab CI'
    "
}

# Verify deployment
verify_deployment() {
    log_info "Verifying PXE server deployment..."

    echo ""
    echo "=========================================="
    echo "Checking services..."

    # Check containers
    ssh_cmd "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep luciverse-pxe"

    echo ""
    echo "Checking HTTP server..."
    if curl -sf "http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}/mac-mapping.json" > /dev/null; then
        log_info "HTTP server responding"
        curl -s "http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}/mac-mapping.json" | head -10
    else
        log_warn "HTTP server not responding yet"
    fi

    echo ""
    echo "Checking boot files..."
    if curl -sf "http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}/boot/vmlinuz" -o /dev/null; then
        log_info "vmlinuz: OK"
    else
        log_warn "vmlinuz: NOT FOUND"
    fi

    if curl -sf "http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}/boot/initramfs.xz" -o /dev/null; then
        log_info "initramfs.xz: OK"
    else
        log_warn "initramfs.xz: NOT FOUND"
    fi
}

# Print usage
print_usage() {
    echo ""
    echo "=========================================="
    echo "LuciVerse Talos PXE Server"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "=========================================="
    echo ""
    echo "PXE Server: http://${ZIMAOS_HOST}:${PXE_HTTP_PORT}"
    echo "Configs:    /DATA/luciverse/talos-configs/"
    echo ""
    echo "Next steps:"
    echo "1. Upload Talos configs to /DATA/luciverse/talos-configs/"
    echo "   (GitLab CI will do this automatically)"
    echo ""
    echo "2. Configure Dell servers for PXE boot:"
    echo "   - F12 during boot for one-time PXE"
    echo "   - Or use iDRAC to set boot order"
    echo ""
    echo "3. Boot servers - they will:"
    echo "   - Get undionly.kpxe via TFTP"
    echo "   - Chain to boot.ipxe"
    echo "   - Download vmlinuz + initramfs"
    echo "   - Fetch config based on MAC"
    echo ""
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "LuciVerse Talos PXE Server Deployment"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "Target: ZimaOS (${ZIMAOS_HOST})"
    echo "=========================================="
    echo ""

    check_deps
    test_connectivity
    setup_directories
    download_assets
    create_ipxe_script
    create_mac_mapping
    deploy_dnsmasq
    deploy_http_server
    create_config_symlinks
    verify_deployment
    print_usage

    echo ""
    log_info "Deployment complete!"
}

main "$@"
