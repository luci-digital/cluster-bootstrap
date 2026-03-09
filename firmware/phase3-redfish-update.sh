#!/bin/bash
# Phase 3: Redfish Firmware Update Script
# Updates Dell PowerEdge cluster firmware via Redfish API
# Date: 2026-01-27

set -e

FIRMWARE_DIR="/home/daryl/cluster-bootstrap/firmware"
HTTP_SERVER="http://192.168.1.145:8000"
LOG_DIR="${FIRMWARE_DIR}/update-logs"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${2:-$NC}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "${LOG_DIR}/update-${TIMESTAMP}.log"
}

# Check if firmware file exists
check_firmware() {
    local file="$1"
    if [ ! -f "${FIRMWARE_DIR}/${file}" ]; then
        log "❌ Firmware file not found: ${file}" "$RED"
        return 1
    fi
    log "✅ Found firmware file: ${file}" "$GREEN"
    return 0
}

# Submit Redfish update job
submit_update() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local firmware_file="$4"
    local description="$5"

    log "🔄 Submitting update for ${description} (${host})" "$BLUE"

    local firmware_url="${HTTP_SERVER}/${firmware_file}"
    log "   Firmware URL: ${firmware_url}" "$NC"

    # Submit SimpleUpdate request
    local response=$(curl -k -s -u "${user}:${pass}" -X POST \
        "https://${host}/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate" \
        -H "Content-Type: application/json" \
        -d "{
            \"ImageURI\": \"${firmware_url}\",
            \"TransferProtocol\": \"HTTP\"
        }" 2>&1)

    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        log "❌ Failed to submit update: curl error $exit_code" "$RED"
        echo "$response" >> "${LOG_DIR}/error-${host}-${TIMESTAMP}.log"
        return 1
    fi

    # Save full response
    echo "$response" > "${LOG_DIR}/response-${host}-${firmware_file}-${TIMESTAMP}.json"

    # Check for task location
    local task_uri=$(echo "$response" | jq -r '.["@odata.id"] // empty')

    if [ -n "$task_uri" ]; then
        log "✅ Update job submitted successfully" "$GREEN"
        log "   Task URI: ${task_uri}" "$NC"
        echo "$task_uri" > "${LOG_DIR}/task-${host}-${firmware_file}.uri"
        return 0
    else
        log "⚠️  Response received but no task URI found" "$YELLOW"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
        return 1
    fi
}

# Monitor task progress
monitor_task() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local task_uri="$4"
    local description="$5"

    log "📊 Monitoring task: ${description}" "$BLUE"

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        sleep 10
        attempt=$((attempt + 1))

        local status=$(curl -k -s -u "${user}:${pass}" "https://${host}${task_uri}" 2>/dev/null)
        local task_state=$(echo "$status" | jq -r '.TaskState // .Oem.Dell.TaskState // "Unknown"')
        local task_status=$(echo "$status" | jq -r '.TaskStatus // .Oem.Dell.TaskStatus // "Unknown"')
        local percent=$(echo "$status" | jq -r '.Oem.Dell.PercentComplete // "N/A"')

        log "   [${attempt}/${max_attempts}] State: ${task_state} | Status: ${task_status} | Progress: ${percent}%" "$NC"

        case "$task_state" in
            "Completed"|"Success")
                log "✅ Task completed successfully!" "$GREEN"
                return 0
                ;;
            "Failed"|"Exception"|"Killed")
                log "❌ Task failed: ${task_status}" "$RED"
                echo "$status" | jq '.' > "${LOG_DIR}/failed-task-${host}-${TIMESTAMP}.json"
                return 1
                ;;
            "Running"|"Starting"|"Downloading"|"Scheduling")
                # Continue monitoring
                ;;
            *)
                log "⚠️  Unknown state: ${task_state}" "$YELLOW"
                ;;
        esac
    done

    log "⏱️  Task monitoring timeout (10 minutes)" "$YELLOW"
    return 2
}

# Check iDRAC availability
check_idrac() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local description="$4"

    log "🔍 Checking iDRAC availability: ${description} (${host})" "$BLUE"

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -k -s -u "${user}:${pass}" "https://${host}/redfish/v1/Managers/iDRAC.Embedded.1" >/dev/null 2>&1; then
            log "✅ iDRAC is responsive" "$GREEN"
            return 0
        fi

        attempt=$((attempt + 1))
        log "   [${attempt}/${max_attempts}] Waiting for iDRAC..." "$NC"
        sleep 10
    done

    log "❌ iDRAC not responding after 5 minutes" "$RED"
    return 1
}

# Verify firmware version after update
verify_version() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local component="$4"
    local description="$5"

    log "🔍 Verifying ${component} version: ${description}" "$BLUE"

    case "$component" in
        "idrac")
            local version=$(curl -k -s -u "${user}:${pass}" "https://${host}/redfish/v1/Managers/iDRAC.Embedded.1" 2>/dev/null | jq -r '.FirmwareVersion')
            ;;
        "bios")
            local version=$(curl -k -s -u "${user}:${pass}" "https://${host}/redfish/v1/Systems/System.Embedded.1" 2>/dev/null | jq -r '.BiosVersion')
            ;;
    esac

    log "   Current ${component} version: ${version}" "$GREEN"
    echo "${version}" > "${LOG_DIR}/version-${host}-${component}-${TIMESTAMP}.txt"
}

# Main update function
update_server() {
    local host="$1"
    local user="$2"
    local pass="$3"
    local firmware_file="$4"
    local component="$5"
    local description="$6"

    log "\n========================================" "$BLUE"
    log "Starting update: ${description}" "$BLUE"
    log "========================================" "$BLUE"

    # Check firmware file exists
    if ! check_firmware "$firmware_file"; then
        log "⏭️  Skipping update - firmware file not available" "$YELLOW"
        return 1
    fi

    # Submit update
    if ! submit_update "$host" "$user" "$pass" "$firmware_file" "$description"; then
        log "❌ Failed to submit update job" "$RED"
        return 1
    fi

    # Get task URI
    local task_uri=$(cat "${LOG_DIR}/task-${host}-${firmware_file}.uri" 2>/dev/null)

    if [ -z "$task_uri" ]; then
        log "⚠️  No task URI available for monitoring" "$YELLOW"
        return 1
    fi

    # Monitor task
    if ! monitor_task "$host" "$user" "$pass" "$task_uri" "$description"; then
        log "⚠️  Task monitoring ended abnormally" "$YELLOW"
    fi

    # For iDRAC updates, wait for reboot
    if [ "$component" = "idrac" ]; then
        log "⏳ Waiting 2 minutes for iDRAC to reboot..." "$YELLOW"
        sleep 120

        if check_idrac "$host" "$user" "$pass" "$description"; then
            verify_version "$host" "$user" "$pass" "$component" "$description"
        fi
    else
        verify_version "$host" "$user" "$pass" "$component" "$description"
    fi

    log "✅ Update process completed for ${description}" "$GREEN"
    return 0
}

# Main execution
main() {
    log "\n╔════════════════════════════════════════════════════════╗" "$BLUE"
    log "║  Phase 3: Dell Cluster Firmware Update via Redfish   ║" "$BLUE"
    log "║  Date: ${TIMESTAMP}                        ║" "$BLUE"
    log "╚════════════════════════════════════════════════════════╝" "$BLUE"

    # Priority 1: R720 iDRAC Update (CRITICAL)
    log "\n🔴 PRIORITY 1: R720 iDRAC Update (CRITICAL)" "$RED"
    update_server "192.168.1.10" "root" "calvin" \
        "r720-idrac-2.70.70.70.BIN" "idrac" "R720 tron iDRAC"

    # Priority 2: R720 BIOS Update
    log "\n🟡 PRIORITY 2: R720 BIOS Update" "$YELLOW"
    update_server "192.168.1.10" "root" "calvin" \
        "r720-bios-2.9.0.BIN" "bios" "R720 tron BIOS"

    # Priority 3: R730 ORION BIOS Update (if server is powered on)
    log "\n🟢 PRIORITY 3: R730 ORION BIOS Update" "$GREEN"
    log "⚠️  Note: R730 ORION is currently powered OFF" "$YELLOW"
    log "   To power on: ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' power on" "$NC"
    # update_server "192.168.1.2" "root" "calvin" \
    #     "r730-bios-2.20.0.BIN" "bios" "R730 ORION BIOS"

    # Priority 4: R730 ESXi5 BIOS Update
    log "\n🟢 PRIORITY 4: R730 ESXi5 BIOS Update" "$GREEN"
    log "⚠️  Note: Server is running VMware ESXi - caution with reboots" "$YELLOW"
    # update_server "192.168.1.32" "root" "calvin" \
    #     "r730-bios-2.20.0.BIN" "bios" "R730 ESXi5 BIOS"

    log "\n╔════════════════════════════════════════════════════════╗" "$BLUE"
    log "║  Update process completed - check logs for details    ║" "$BLUE"
    log "║  Logs: ${LOG_DIR}              ║" "$BLUE"
    log "╚════════════════════════════════════════════════════════╝" "$BLUE"
}

# Run main function
main "$@"
