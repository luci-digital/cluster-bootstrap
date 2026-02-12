#!/bin/bash
# Deploy Supermicro GPU Server to LuciVerse Cluster
# Server: S213078X5B29794
# Tier: COMN (528 Hz)
# Genesis Bond: ACTIVE

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Configuration
BMC_IP="192.168.1.165"
BMC_USER="ADMIN"
BMC_PASS="password@123"
PLANNED_IP="192.168.1.170"
PLANNED_IP6="2602:F674:0001::170/64"
TIER="COMN"
FREQUENCY="528"

log_info "=============================================="
log_info "Supermicro GPU-1 Cluster Deployment"
log_info "Tier: COMN @ 528 Hz"
log_info "=============================================="
echo ""

# Step 1: Clear old event log
clear_event_log() {
    log_info "Step 1: Clearing BMC event log..."

    RESULT=$(curl -k -s -X POST -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1/LogServices/Log1/Actions/LogService.ClearLog \
        -H "Content-Type: application/json" -d '{}' -w "%{http_code}" -o /dev/null)

    if [ "$RESULT" = "200" ] || [ "$RESULT" = "204" ]; then
        log_success "Event log cleared"
    else
        log_warning "Could not clear event log (HTTP $RESULT)"
    fi
}

# Step 2: Check current power state
check_power_state() {
    log_info "Step 2: Checking power state..."

    POWER_STATE=$(curl -k -s -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1 | \
        python3 -c "import sys,json; print(json.load(sys.stdin)['PowerState'])")

    log_info "Power state: $POWER_STATE"

    if [ "$POWER_STATE" = "Off" ]; then
        log_warning "Server is powered off"
        read -p "Power on server? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            power_on_server
        else
            log_error "Cannot continue with server powered off"
            exit 1
        fi
    else
        log_success "Server is powered on"
    fi
}

# Step 3: Power on if needed
power_on_server() {
    log_info "Powering on server..."

    curl -k -s -X POST -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1/Actions/ComputerSystem.Reset \
        -H "Content-Type: application/json" \
        -d '{"ResetType": "On"}' > /dev/null

    log_success "Power on command sent"
    log_info "Waiting 30 seconds for boot..."
    sleep 30
}

# Step 4: Enable PXE boot
enable_pxe_boot() {
    log_info "Step 3: Enabling PXE boot (one-time)..."

    curl -k -s -X PATCH -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1 \
        -H "Content-Type: application/json" \
        -d '{
          "Boot": {
            "BootSourceOverrideEnabled": "Once",
            "BootSourceOverrideTarget": "Pxe"
          }
        }' > /dev/null

    log_success "PXE boot enabled for next restart"
}

# Step 5: Check network status
check_network() {
    log_info "Step 4: Checking network interfaces..."

    NIC1_STATUS=$(curl -k -s -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1/EthernetInterfaces/1 | \
        python3 -c "import sys,json; print(json.load(sys.stdin)['Status']['State'])")

    log_info "NIC1 (0c:c4:7a:a8:72:14): $NIC1_STATUS"

    if [ "$NIC1_STATUS" = "Disabled" ]; then
        log_warning "Network interface disabled - cable not connected"
        log_warning "Please connect network cable to eth0 before proceeding"
        read -p "Press enter when cable is connected..."
    else
        log_success "Network interface active"
    fi
}

# Step 6: Restart to PXE boot
restart_to_pxe() {
    log_info "Step 5: Restarting to PXE boot..."

    curl -k -s -X POST -u "$BMC_USER:$BMC_PASS" \
        https://$BMC_IP/redfish/v1/Systems/1/Actions/ComputerSystem.Reset \
        -H "Content-Type: application/json" \
        -d '{"ResetType": "ForceRestart"}' > /dev/null

    log_success "Restart command sent"
    log_info "Server will PXE boot from 192.168.1.146"
}

# Step 7: Monitor via KVM
show_kvm_info() {
    log_info "Step 6: Monitoring installation..."
    echo ""
    log_info "You can monitor the installation via:"
    log_info "  Web KVM: https://$BMC_IP"
    log_info "  Username: $BMC_USER"
    log_info "  Password: $BMC_PASS"
    echo ""
    log_info "Navigate to: Remote Control -> Console Redirection"
    echo ""
}

# Step 8: Wait for registration
wait_for_registration() {
    log_info "Step 7: Waiting for server registration..."
    log_info "MAC: 0c:c4:7a:a8:72:14"
    log_info "Expected IP: $PLANNED_IP"
    log_info "Expected IPv6: $PLANNED_IP6"
    echo ""
    log_info "The server will automatically:"
    log_info "  1. Boot via PXE from zbook (192.168.1.146)"
    log_info "  2. Download NixOS installer"
    log_info "  3. Register MAC with provision-listener"
    log_info "  4. Install NixOS with COMN tier config"
    log_info "  5. Join Ray cluster @ 528 Hz"
    echo ""
    log_info "Check provision listener logs:"
    log_info "  journalctl -u luciverse-provision -f"
}

# Main execution
main() {
    clear_event_log
    echo ""

    check_power_state
    echo ""

    enable_pxe_boot
    echo ""

    check_network
    echo ""

    log_info "Ready to deploy?"
    read -p "Continue with PXE boot? (y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        restart_to_pxe
        echo ""

        show_kvm_info
        wait_for_registration

        log_success "Deployment initiated!"
        log_info "Server should be operational in 10-15 minutes"
    else
        log_warning "Deployment cancelled"
        exit 0
    fi
}

# Run
main "$@"
