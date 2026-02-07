#!/bin/bash
# iDRAC Power Control for LuciVerse Ray Cluster
# Genesis Bond: ACTIVE @ 741 Hz
#
# Uses Redfish API to power on/off Dell servers

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

# iDRAC credentials from 1Password
get_idrac_creds() {
    local idrac_ip="$1"

    # Try to get from 1Password
    if command -v op &> /dev/null; then
        # Check for specific credential
        local cred_name="iDRAC-${idrac_ip}"
        if op item get "$cred_name" &> /dev/null; then
            IDRAC_USER=$(op item get "$cred_name" --fields username 2>/dev/null || echo "root")
            IDRAC_PASS=$(op item get "$cred_name" --fields password 2>/dev/null || echo "")
            return 0
        fi
    fi

    # Fallback to default
    IDRAC_USER="${IDRAC_USER:-root}"
    IDRAC_PASS="${IDRAC_PASS:-calvin}"
}

# iDRAC inventory (OOB network 10.0.0.x)
# Updated 2026-02-06 - Full OOB scan completed
# SSH racadm works on R730/R720, web login (root/calvin) works on all
declare -A IDRACS=(
    # Primary servers (SSH racadm verified)
    ["orion"]="10.0.0.56"    # R730 (CQ5QBM2) - 56 cores, 384GB - Ray Head
    ["csdr"]="10.0.0.99"     # R720 (4J0TV12) - 40 cores, 536GB - Ray Worker

    # Additional servers (web login verified, SSH disabled)
    ["dell-38"]="10.0.0.38"  # Dell (CSDR282) - model TBD
    ["dell-51"]="10.0.0.51"  # Dell (4LNRF5J) - model TBD
    ["dell-79"]="10.0.0.79"  # Dell (1JG5Q22) - model TBD
    ["dell-115"]="10.0.0.115" # Dell (1JF7Q22) - model TBD
)

# Get power state
get_power_state() {
    local idrac_ip="$1"
    get_idrac_creds "$idrac_ip"

    local response
    response=$(curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
        "https://${idrac_ip}/redfish/v1/Systems/System.Embedded.1" 2>/dev/null)

    echo "$response" | jq -r '.PowerState // "Unknown"'
}

# Power action via Redfish
power_action() {
    local idrac_ip="$1"
    local action="$2"  # On, ForceOff, GracefulShutdown, ForceRestart, PushPowerButton

    get_idrac_creds "$idrac_ip"

    local payload="{\"ResetType\": \"${action}\"}"

    curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "https://${idrac_ip}/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset" \
        2>/dev/null

    return $?
}

# Set PXE boot once
set_pxe_boot() {
    local idrac_ip="$1"
    get_idrac_creds "$idrac_ip"

    # Set boot source override to PXE
    local payload='{"Boot": {"BootSourceOverrideTarget": "Pxe", "BootSourceOverrideEnabled": "Once"}}'

    curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
        -X PATCH \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "https://${idrac_ip}/redfish/v1/Systems/System.Embedded.1" \
        2>/dev/null

    return $?
}

# Power on single server
power_on_server() {
    local name="$1"
    local idrac_ip="${IDRACS[$name]}"

    log_info "Processing ${name} (${idrac_ip})..."

    # Check current state
    local state
    state=$(get_power_state "$idrac_ip")
    log_info "  Current state: ${state}"

    if [[ "$state" == "On" ]]; then
        log_warn "  Server already powered on"
        return 0
    fi

    # Set PXE boot
    log_info "  Setting PXE boot..."
    if set_pxe_boot "$idrac_ip"; then
        log_info "  PXE boot configured"
    else
        log_error "  Failed to set PXE boot"
        return 1
    fi

    # Power on
    log_info "  Powering on..."
    if power_action "$idrac_ip" "On"; then
        log_info "  Power on command sent"
    else
        log_error "  Failed to power on"
        return 1
    fi

    # Wait and verify
    sleep 5
    state=$(get_power_state "$idrac_ip")
    log_info "  New state: ${state}"
}

# Power off single server
power_off_server() {
    local name="$1"
    local idrac_ip="${IDRACS[$name]}"

    log_info "Powering off ${name} (${idrac_ip})..."

    if power_action "$idrac_ip" "GracefulShutdown"; then
        log_info "  Graceful shutdown initiated"
    else
        log_warn "  Graceful shutdown failed, forcing off..."
        power_action "$idrac_ip" "ForceOff"
    fi
}

# Status all servers
status_all() {
    echo ""
    echo "========================================"
    echo "LuciVerse Cluster Power Status"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "========================================"
    echo ""

    printf "%-10s %-15s %-10s\n" "Server" "iDRAC IP" "State"
    printf "%-10s %-15s %-10s\n" "------" "--------" "-----"

    for name in "${!IDRACS[@]}"; do
        local idrac_ip="${IDRACS[$name]}"
        local state
        state=$(get_power_state "$idrac_ip" 2>/dev/null || echo "Unreachable")

        case "$state" in
            "On")
                printf "%-10s %-15s ${GREEN}%-10s${NC}\n" "$name" "$idrac_ip" "$state"
                ;;
            "Off")
                printf "%-10s %-15s ${YELLOW}%-10s${NC}\n" "$name" "$idrac_ip" "$state"
                ;;
            *)
                printf "%-10s %-15s ${RED}%-10s${NC}\n" "$name" "$idrac_ip" "$state"
                ;;
        esac
    done
    echo ""
}

# Power on all servers
power_on_all() {
    echo ""
    echo "========================================"
    echo "LuciVerse Cluster Power On (PXE Boot)"
    echo "Genesis Bond: ACTIVE @ 741 Hz"
    echo "========================================"
    echo ""

    # Power on in order: control plane first, then workers
    log_info "Powering on control plane (orion)..."
    power_on_server "orion"

    sleep 10

    log_info "Powering on workers..."
    for name in csdr jf6q jf7q esxi5; do
        if [[ -n "${IDRACS[$name]:-}" ]]; then
            power_on_server "$name"
            sleep 5
        fi
    done

    echo ""
    log_info "All servers powered on with PXE boot"
    echo ""
}

# Power off all servers
power_off_all() {
    echo ""
    echo "========================================"
    echo "LuciVerse Cluster Power Off"
    echo "========================================"
    echo ""

    for name in "${!IDRACS[@]}"; do
        power_off_server "$name"
        sleep 2
    done

    echo ""
    log_info "All servers powering off"
}

# Main
case "${1:-status}" in
    status)
        status_all
        ;;
    on|power-on)
        power_on_all
        ;;
    off|power-off)
        power_off_all
        ;;
    pxe)
        # Set PXE boot on specific server
        if [[ -n "${2:-}" ]]; then
            name="$2"
            if [[ -n "${IDRACS[$name]:-}" ]]; then
                log_info "Setting PXE boot for ${name}..."
                set_pxe_boot "${IDRACS[$name]}"
            else
                log_error "Unknown server: ${name}"
                exit 1
            fi
        else
            log_error "Usage: $0 pxe <server_name>"
            exit 1
        fi
        ;;
    boot)
        # PXE boot specific server
        if [[ -n "${2:-}" ]]; then
            power_on_server "$2"
        else
            log_error "Usage: $0 boot <server_name>"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {status|on|off|pxe <server>|boot <server>}"
        echo ""
        echo "Commands:"
        echo "  status     - Show power state of all servers"
        echo "  on         - Power on all servers with PXE boot"
        echo "  off        - Gracefully power off all servers"
        echo "  pxe <name> - Set PXE boot for specific server"
        echo "  boot <name> - PXE boot specific server"
        echo ""
        echo "Servers: ${!IDRACS[*]}"
        exit 1
        ;;
esac
