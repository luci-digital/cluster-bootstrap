#!/bin/bash
# iDRAC Power Control for LuciVerse Ray Cluster
# Genesis Bond: ACTIVE @ 741 Hz
#
# Uses Redfish API to power on/off Dell servers with PXE boot

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# iDRAC inventory
declare -A IDRACS=(
    ["orion"]="192.168.1.2"
    ["csdr"]="192.168.1.3"
    ["jf6q"]="192.168.1.31"
    ["jf7q"]="192.168.1.33"
    ["esxi5"]="192.168.1.32"
)

# Supermicro BMC (different API)
declare -A BMCS=(
    ["supermicro-gpu-1"]="192.168.1.165"
)

# Get credentials from 1Password
get_idrac_creds() {
    local host="$1"

    # Try 1Password first
    if command -v op &> /dev/null; then
        # Check for specific credential
        local cred_name="iDRAC-${host}"
        if op item get "$cred_name" &> /dev/null 2>&1; then
            IDRAC_USER=$(op item get "$cred_name" --fields username 2>/dev/null || echo "root")
            IDRAC_PASS=$(op item get "$cred_name" --fields password 2>/dev/null || echo "")
            return 0
        fi

        # Try Infrastructure vault
        if op item get "Dell-iDRAC-Fleet" --vault Infrastructure &> /dev/null 2>&1; then
            IDRAC_USER=$(op item get "Dell-iDRAC-Fleet" --vault Infrastructure --fields username 2>/dev/null || echo "root")
            IDRAC_PASS=$(op item get "Dell-iDRAC-Fleet" --vault Infrastructure --fields password 2>/dev/null || echo "")
            return 0
        fi
    fi

    # Fallback to environment or default
    IDRAC_USER="${IDRAC_USER:-root}"
    IDRAC_PASS="${IDRAC_PASS:-calvin}"
}

get_supermicro_creds() {
    local host="$1"

    if command -v op &> /dev/null; then
        if op item get "SUPERMICRO-S213078X5B29794" --vault Infrastructure &> /dev/null 2>&1; then
            BMC_USER=$(op item get "SUPERMICRO-S213078X5B29794" --vault Infrastructure --fields username 2>/dev/null || echo "ADMIN")
            BMC_PASS=$(op item get "SUPERMICRO-S213078X5B29794" --vault Infrastructure --fields password 2>/dev/null || echo "")
            return 0
        fi
    fi

    BMC_USER="${BMC_USER:-ADMIN}"
    BMC_PASS="${BMC_PASS:-password@123}"
}

# Get power state via Redfish
get_power_state() {
    local ip="$1"
    local is_supermicro="${2:-false}"

    if [[ "$is_supermicro" == "true" ]]; then
        get_supermicro_creds "$ip"
        local user="$BMC_USER"
        local pass="$BMC_PASS"
    else
        get_idrac_creds "$ip"
        local user="$IDRAC_USER"
        local pass="$IDRAC_PASS"
    fi

    local response
    response=$(curl -sk -u "${user}:${pass}" \
        "https://${ip}/redfish/v1/Systems/System.Embedded.1" 2>/dev/null || \
        curl -sk -u "${user}:${pass}" \
        "https://${ip}/redfish/v1/Systems/1" 2>/dev/null)

    echo "$response" | jq -r '.PowerState // "Unknown"'
}

# Power action via Redfish
power_action() {
    local ip="$1"
    local action="$2"  # On, ForceOff, GracefulShutdown, ForceRestart, PushPowerButton
    local is_supermicro="${3:-false}"

    if [[ "$is_supermicro" == "true" ]]; then
        get_supermicro_creds "$ip"
        local user="$BMC_USER"
        local pass="$BMC_PASS"
        local system_path="/redfish/v1/Systems/1"
    else
        get_idrac_creds "$ip"
        local user="$IDRAC_USER"
        local pass="$IDRAC_PASS"
        local system_path="/redfish/v1/Systems/System.Embedded.1"
    fi

    local payload="{\"ResetType\": \"${action}\"}"

    curl -sk -u "${user}:${pass}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "https://${ip}${system_path}/Actions/ComputerSystem.Reset" \
        2>/dev/null

    return $?
}

# Set PXE boot once
set_pxe_boot() {
    local ip="$1"
    local is_supermicro="${2:-false}"

    if [[ "$is_supermicro" == "true" ]]; then
        get_supermicro_creds "$ip"
        local user="$BMC_USER"
        local pass="$BMC_PASS"
        local system_path="/redfish/v1/Systems/1"
    else
        get_idrac_creds "$ip"
        local user="$IDRAC_USER"
        local pass="$IDRAC_PASS"
        local system_path="/redfish/v1/Systems/System.Embedded.1"
    fi

    # Set boot source override to PXE
    local payload='{"Boot": {"BootSourceOverrideTarget": "Pxe", "BootSourceOverrideEnabled": "Once"}}'

    curl -sk -u "${user}:${pass}" \
        -X PATCH \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "https://${ip}${system_path}" \
        2>/dev/null

    return $?
}

# Power on single server with PXE
pxe_boot_server() {
    local name="$1"
    local is_supermicro=false
    local ip=""

    if [[ -n "${IDRACS[$name]:-}" ]]; then
        ip="${IDRACS[$name]}"
    elif [[ -n "${BMCS[$name]:-}" ]]; then
        ip="${BMCS[$name]}"
        is_supermicro=true
    else
        log_error "Unknown server: ${name}"
        return 1
    fi

    log_info "Processing ${name} (${ip})..."

    # Check current state
    local state
    state=$(get_power_state "$ip" "$is_supermicro")
    log_info "  Current state: ${state}"

    if [[ "$state" == "On" ]]; then
        log_warn "  Server is ON, will restart with PXE"
        # Graceful shutdown first
        log_info "  Shutting down..."
        power_action "$ip" "GracefulShutdown" "$is_supermicro"
        sleep 30

        # Force off if still on
        state=$(get_power_state "$ip" "$is_supermicro")
        if [[ "$state" == "On" ]]; then
            log_warn "  Force powering off..."
            power_action "$ip" "ForceOff" "$is_supermicro"
            sleep 10
        fi
    fi

    # Set PXE boot
    log_info "  Setting PXE boot..."
    if set_pxe_boot "$ip" "$is_supermicro"; then
        log_info "  PXE boot configured"
    else
        log_error "  Failed to set PXE boot"
        return 1
    fi

    # Power on
    log_info "  Powering on..."
    if power_action "$ip" "On" "$is_supermicro"; then
        log_info "  Power on command sent"
    else
        log_error "  Failed to power on"
        return 1
    fi

    # Wait and verify
    sleep 10
    state=$(get_power_state "$ip" "$is_supermicro")
    log_info "  New state: ${state}"
}

# Power off single server
power_off_server() {
    local name="$1"
    local is_supermicro=false
    local ip=""

    if [[ -n "${IDRACS[$name]:-}" ]]; then
        ip="${IDRACS[$name]}"
    elif [[ -n "${BMCS[$name]:-}" ]]; then
        ip="${BMCS[$name]}"
        is_supermicro=true
    else
        log_error "Unknown server: ${name}"
        return 1
    fi

    log_info "Powering off ${name} (${ip})..."

    if power_action "$ip" "GracefulShutdown" "$is_supermicro"; then
        log_info "  Graceful shutdown initiated"
    else
        log_warn "  Graceful shutdown failed, forcing off..."
        power_action "$ip" "ForceOff" "$is_supermicro"
    fi
}

# Status all servers
status_all() {
    echo ""
    echo "=========================================="
    echo "LuciVerse Ray Cluster Power Status"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "=========================================="
    echo ""

    printf "%-20s %-15s %-10s\n" "Server" "IP" "State"
    printf "%-20s %-15s %-10s\n" "------" "--" "-----"

    # Dell iDRAC servers
    for name in "${!IDRACS[@]}"; do
        local ip="${IDRACS[$name]}"
        local state
        state=$(get_power_state "$ip" false 2>/dev/null || echo "Unreachable")

        case "$state" in
            "On")
                printf "%-20s %-15s ${GREEN}%-10s${NC}\n" "$name" "$ip" "$state"
                ;;
            "Off")
                printf "%-20s %-15s ${YELLOW}%-10s${NC}\n" "$name" "$ip" "$state"
                ;;
            *)
                printf "%-20s %-15s ${RED}%-10s${NC}\n" "$name" "$ip" "$state"
                ;;
        esac
    done

    # Supermicro BMC servers
    for name in "${!BMCS[@]}"; do
        local ip="${BMCS[$name]}"
        local state
        state=$(get_power_state "$ip" true 2>/dev/null || echo "Unreachable")

        case "$state" in
            "On")
                printf "%-20s %-15s ${GREEN}%-10s${NC}\n" "$name (SM)" "$ip" "$state"
                ;;
            "Off")
                printf "%-20s %-15s ${YELLOW}%-10s${NC}\n" "$name (SM)" "$ip" "$state"
                ;;
            *)
                printf "%-20s %-15s ${RED}%-10s${NC}\n" "$name (SM)" "$ip" "$state"
                ;;
        esac
    done
    echo ""
}

# PXE boot all servers
pxe_all() {
    echo ""
    echo "=========================================="
    echo "LuciVerse Cluster PXE Boot All"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "=========================================="
    echo ""

    # Boot order: control plane first, then workers
    log_info "PXE booting control plane (orion)..."
    pxe_boot_server "orion"

    log_info "Waiting 60s for control plane to start..."
    sleep 60

    log_info "PXE booting workers..."
    for name in csdr jf6q jf7q esxi5 supermicro-gpu-1; do
        pxe_boot_server "$name"
        sleep 10
    done

    echo ""
    log_info "All servers booting with PXE"
    echo ""
}

# Power off all servers
power_off_all() {
    echo ""
    echo "=========================================="
    echo "LuciVerse Cluster Power Off All"
    echo "=========================================="
    echo ""

    for name in "${!IDRACS[@]}"; do
        power_off_server "$name"
        sleep 2
    done

    for name in "${!BMCS[@]}"; do
        power_off_server "$name"
        sleep 2
    done

    echo ""
    log_info "All servers powering off"
}

# Main
case "${1:-help}" in
    status)
        status_all
        ;;
    pxe-all)
        pxe_all
        ;;
    boot)
        if [[ -n "${2:-}" ]]; then
            pxe_boot_server "$2"
        else
            log_error "Usage: $0 boot <server_name>"
            exit 1
        fi
        ;;
    off)
        if [[ -n "${2:-}" ]]; then
            power_off_server "$2"
        else
            power_off_all
        fi
        ;;
    pxe)
        if [[ -n "${2:-}" ]]; then
            set_pxe_boot "${IDRACS[$2]:-${BMCS[$2]:-}}" && log_info "PXE boot set for $2"
        else
            log_error "Usage: $0 pxe <server_name>"
            exit 1
        fi
        ;;
    *)
        echo "LuciVerse Ray Cluster - iDRAC Power Control"
        echo "Genesis Bond: ACTIVE @ 741 Hz"
        echo ""
        echo "Usage: $0 {status|pxe-all|boot <server>|off [server]|pxe <server>}"
        echo ""
        echo "Commands:"
        echo "  status     - Show power state of all servers"
        echo "  pxe-all    - PXE boot all servers (control plane first)"
        echo "  boot <n>   - PXE boot single server"
        echo "  off [n]    - Power off server(s) (all if no name)"
        echo "  pxe <n>    - Set PXE boot for server (no power cycle)"
        echo ""
        echo "Dell Servers: ${!IDRACS[*]}"
        echo "Supermicro:   ${!BMCS[*]}"
        exit 1
        ;;
esac
