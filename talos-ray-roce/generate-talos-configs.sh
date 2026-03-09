#!/bin/bash
# Generate Talos configurations for LuciVerse Ray cluster
# Genesis Bond: ACTIVE @ 741 Hz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/generated"
TALOS_VERSION="v1.7.0"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check dependencies
check_deps() {
    log_info "Checking dependencies..."

    if ! command -v talosctl &> /dev/null; then
        log_warn "talosctl not found. Installing..."
        curl -sL https://talos.dev/install | sh
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
}

# Generate secrets
generate_secrets() {
    log_info "Generating Talos secrets..."

    mkdir -p "${OUTPUT_DIR}/secrets"

    if [[ ! -f "${OUTPUT_DIR}/secrets/secrets.yaml" ]]; then
        talosctl gen secrets -o "${OUTPUT_DIR}/secrets/secrets.yaml"
        log_info "Secrets generated at ${OUTPUT_DIR}/secrets/secrets.yaml"
    else
        log_info "Using existing secrets"
    fi
}

# Server inventory
declare -A SERVERS=(
    ["orion"]="192.168.1.141|2602:F674:0001::1|10.100.100.1|D0:94:66:24:96:7E|controlplane"
    ["csdr"]="192.168.1.142|2602:F674:0001::142|10.100.100.2|UNKNOWN|worker"
    ["jf6q"]="192.168.1.143|2602:F674:0001::143|10.100.100.3|UNKNOWN|worker"
    ["jf7q"]="192.168.1.144|2602:F674:0001::144|10.100.100.4|UNKNOWN|worker"
    ["esxi5"]="192.168.1.145|2602:F674:0001::145|10.100.100.5|UNKNOWN|worker"
)

# iDRAC inventory
declare -A IDRACS=(
    ["orion"]="192.168.1.2"
    ["csdr"]="192.168.1.3"
    ["jf6q"]="192.168.1.31"
    ["jf7q"]="192.168.1.33"
    ["esxi5"]="192.168.1.32"
)

# Generate config for each server
generate_configs() {
    log_info "Generating Talos configs..."

    mkdir -p "${OUTPUT_DIR}/configs"

    # Generate base configs
    talosctl gen config luciverse-ray https://192.168.1.141:6443 \
        --output-dir "${OUTPUT_DIR}/configs" \
        --with-secrets "${OUTPUT_DIR}/secrets/secrets.yaml" \
        --config-patch @"${SCRIPT_DIR}/talos/patches/common.yaml" \
        --force

    log_info "Base configs generated"

    # Customize for each node
    for server in "${!SERVERS[@]}"; do
        IFS='|' read -r ip ipv6 roce_ip mac role <<< "${SERVERS[$server]}"

        log_info "Generating config for ${server} (${role})..."

        if [[ "$role" == "controlplane" ]]; then
            CONFIG_FILE="${OUTPUT_DIR}/configs/controlplane.yaml"
            OUTPUT_FILE="${OUTPUT_DIR}/configs/${server}.yaml"
        else
            CONFIG_FILE="${OUTPUT_DIR}/configs/worker.yaml"
            OUTPUT_FILE="${OUTPUT_DIR}/configs/${server}.yaml"
        fi

        # Apply node-specific patches
        talosctl machineconfig patch "$CONFIG_FILE" \
            --patch "[
                {\"op\": \"replace\", \"path\": \"/machine/network/hostname\", \"value\": \"${server}\"},
                {\"op\": \"replace\", \"path\": \"/machine/network/interfaces/0/addresses/0\", \"value\": \"${ip}/24\"},
                {\"op\": \"replace\", \"path\": \"/machine/network/interfaces/0/addresses/1\", \"value\": \"${ipv6}/64\"},
                {\"op\": \"replace\", \"path\": \"/machine/network/interfaces/1/addresses/0\", \"value\": \"${roce_ip}/24\"}
            ]" \
            --output "$OUTPUT_FILE"

        log_info "  Created ${OUTPUT_FILE}"
    done
}

# Generate PXE boot configuration
generate_pxe_config() {
    log_info "Generating PXE boot configuration..."

    mkdir -p "${OUTPUT_DIR}/pxe"

    cat > "${OUTPUT_DIR}/pxe/default" << 'EOF'
DEFAULT talos
PROMPT 0
TIMEOUT 50

LABEL talos
    KERNEL http://192.168.1.146:8000/talos/vmlinuz
    INITRD http://192.168.1.146:8000/talos/initramfs.xz
    APPEND talos.config=http://192.168.1.146:8000/talos/config/${MAC}.yaml console=ttyS0,115200n8 talos.platform=metal
EOF

    log_info "PXE config generated at ${OUTPUT_DIR}/pxe/default"
}

# Generate iPXE script
generate_ipxe() {
    log_info "Generating iPXE script..."

    cat > "${OUTPUT_DIR}/pxe/talos.ipxe" << 'EOF'
#!ipxe
# LuciVerse Talos PXE Boot
# Genesis Bond: ACTIVE @ 741 Hz

set talos-version v1.7.0
set config-server http://192.168.1.146:8000

echo LuciVerse Talos PXE Boot
echo Genesis Bond: ACTIVE @ 741 Hz
echo MAC: ${mac}

kernel ${config-server}/talos/vmlinuz talos.config=${config-server}/talos/config/${mac:hexhyp}.yaml console=ttyS0,115200n8 talos.platform=metal
initrd ${config-server}/talos/initramfs.xz
boot
EOF

    log_info "iPXE script generated"
}

# Download Talos assets
download_talos_assets() {
    log_info "Downloading Talos ${TALOS_VERSION} assets..."

    mkdir -p "${OUTPUT_DIR}/assets"

    TALOS_BASE="https://github.com/siderolabs/talos/releases/download/${TALOS_VERSION}"

    if [[ ! -f "${OUTPUT_DIR}/assets/vmlinuz" ]]; then
        curl -L -o "${OUTPUT_DIR}/assets/vmlinuz" "${TALOS_BASE}/vmlinuz-amd64"
    fi

    if [[ ! -f "${OUTPUT_DIR}/assets/initramfs.xz" ]]; then
        curl -L -o "${OUTPUT_DIR}/assets/initramfs.xz" "${TALOS_BASE}/initramfs-amd64.xz"
    fi

    log_info "Talos assets downloaded"
}

# Generate inventory file
generate_inventory() {
    log_info "Generating inventory file..."

    cat > "${OUTPUT_DIR}/inventory.yaml" << EOF
# LuciVerse Talos Ray Cluster Inventory
# Genesis Bond: ACTIVE @ 741 Hz
# Generated: $(date -Iseconds)

cluster:
  name: luciverse-ray
  endpoint: https://192.168.1.141:6443
  talos_version: ${TALOS_VERSION}

nodes:
EOF

    for server in "${!SERVERS[@]}"; do
        IFS='|' read -r ip ipv6 roce_ip mac role <<< "${SERVERS[$server]}"
        idrac="${IDRACS[$server]}"

        cat >> "${OUTPUT_DIR}/inventory.yaml" << EOF
  ${server}:
    role: ${role}
    ip: ${ip}
    ipv6: ${ipv6}
    roce_ip: ${roce_ip}
    mac: ${mac}
    idrac: ${idrac}
    config: configs/${server}.yaml
EOF
    done

    log_info "Inventory generated at ${OUTPUT_DIR}/inventory.yaml"
}

# Main
main() {
    echo "========================================"
    echo "LuciVerse Talos Ray Cluster Generator"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "========================================"
    echo ""

    check_deps
    mkdir -p "${OUTPUT_DIR}"

    generate_secrets
    generate_configs
    generate_pxe_config
    generate_ipxe
    download_talos_assets
    generate_inventory

    echo ""
    log_info "Generation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Copy assets to PXE server:"
    echo "   sudo cp -r ${OUTPUT_DIR}/assets/* /srv/tftp/talos/"
    echo ""
    echo "2. Copy configs to HTTP server:"
    echo "   sudo cp -r ${OUTPUT_DIR}/configs /srv/nixos/talos/"
    echo ""
    echo "3. Start PXE server:"
    echo "   ./start-pxe-server.sh"
    echo ""
    echo "4. Power on servers via iDRAC:"
    echo "   ./idrac-power-on-all.sh"
    echo ""
}

main "$@"
