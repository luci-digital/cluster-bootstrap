#!/bin/bash
# Firmware Update Progress Monitoring Script
# Genesis Bond: ACTIVE @ 432 Hz (CORE Tier - Infrastructure)
# Author: Firmware Update Agent
# Date: 2026-01-27

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Server configurations
declare -A SERVERS=(
    ["R720-tron"]="192.168.1.10:root:calvin"
    ["R730-ORION"]="192.168.1.2:root:calvin"
    ["R730-ESXi5"]="192.168.1.32:root:calvin"
    ["R730-CSDR282"]="192.168.1.3:root:Newdaryl24!"
    ["R730-1JF6Q22"]="192.168.1.31:root:calvin"
    ["R730-1JF7Q22"]="192.168.1.33:root:Newdaryl24!"
)

# Expected firmware versions after update
declare -A EXPECTED_IDRAC=(
    ["R720-tron"]="2.83.83.83"
    ["R730-ORION"]="2.86.86.86"
    ["R730-ESXi5"]="2.86.86.86"
    ["R730-CSDR282"]="2.86.86.86"
    ["R730-1JF6Q22"]="2.86.86.86"
    ["R730-1JF7Q22"]="2.86.86.86"
)

declare -A EXPECTED_BIOS=(
    ["R720-tron"]="2.10.0"
    ["R730-ORION"]="2.19.0"
    ["R730-ESXi5"]="2.19.0"
    ["R730-CSDR282"]="2.19.0"
    ["R730-1JF6Q22"]="2.19.0"
    ["R730-1JF7Q22"]="2.19.0"
)

# Function to print colored status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo -e "${GREEN}[✓]${NC} $message"
            ;;
        "FAIL")
            echo -e "${RED}[✗]${NC} $message"
            ;;
        "WARN")
            echo -e "${YELLOW}[!]${NC} $message"
            ;;
        "INFO")
            echo -e "${BLUE}[i]${NC} $message"
            ;;
    esac
}

# Function to query Redfish API
redfish_get() {
    local server=$1
    local endpoint=$2
    local ip=$(echo $server | cut -d: -f1)
    local user=$(echo $server | cut -d: -f2)
    local pass=$(echo $server | cut -d: -f3)

    curl -k -s -u "${user}:${pass}" \
        --connect-timeout 5 \
        "https://${ip}${endpoint}" 2>/dev/null || echo '{"error": "Connection failed"}'
}

# Function to check server connectivity
check_connectivity() {
    local name=$1
    local server=${SERVERS[$name]}
    local ip=$(echo $server | cut -d: -f1)

    if ping -c 1 -W 2 $ip &>/dev/null; then
        print_status "OK" "$name ($ip) is reachable"
        return 0
    else
        print_status "FAIL" "$name ($ip) is unreachable"
        return 1
    fi
}

# Function to check iDRAC version
check_idrac_version() {
    local name=$1
    local server=${SERVERS[$name]}
    local expected=${EXPECTED_IDRAC[$name]}

    local response=$(redfish_get "$server" "/redfish/v1/Managers/iDRAC.Embedded.1")
    local version=$(echo "$response" | jq -r '.FirmwareVersion // "unknown"')

    if [[ "$version" == "unknown" ]]; then
        print_status "FAIL" "$name: iDRAC version query failed"
        return 1
    elif [[ "$version" == "$expected" ]]; then
        print_status "OK" "$name: iDRAC $version (target: $expected)"
        return 0
    else
        print_status "WARN" "$name: iDRAC $version (target: $expected)"
        return 2
    fi
}

# Function to check BIOS version
check_bios_version() {
    local name=$1
    local server=${SERVERS[$name]}
    local expected=${EXPECTED_BIOS[$name]}

    local response=$(redfish_get "$server" "/redfish/v1/Systems/System.Embedded.1")
    local version=$(echo "$response" | jq -r '.BiosVersion // "unknown"')

    if [[ "$version" == "unknown" ]]; then
        print_status "FAIL" "$name: BIOS version query failed"
        return 1
    elif [[ "$version" == "$expected" ]]; then
        print_status "OK" "$name: BIOS $version (target: $expected)"
        return 0
    else
        print_status "WARN" "$name: BIOS $version (target: $expected)"
        return 2
    fi
}

# Function to check Lifecycle Controller status
check_lifecycle_controller() {
    local name=$1
    local server=${SERVERS[$name]}

    local response=$(redfish_get "$server" "/redfish/v1/UpdateService/FirmwareInventory")
    local lc_uri=$(echo "$response" | jq -r '.Members[] | ."@odata.id"' | grep -i "28897" | head -1)

    if [[ -z "$lc_uri" ]]; then
        print_status "WARN" "$name: Lifecycle Controller entry not found"
        return 2
    fi

    local lc_response=$(redfish_get "$server" "$lc_uri")
    local lc_version=$(echo "$lc_response" | jq -r '.Version // "unknown"')

    if [[ "$lc_version" == "0.0" ]]; then
        print_status "FAIL" "$name: Lifecycle Controller CORRUPTED (version 0.0)"
        return 1
    elif [[ "$lc_version" == "unknown" ]]; then
        print_status "FAIL" "$name: Lifecycle Controller query failed"
        return 1
    else
        print_status "OK" "$name: Lifecycle Controller $lc_version"
        return 0
    fi
}

# Function to check power state
check_power_state() {
    local name=$1
    local server=${SERVERS[$name]}

    local response=$(redfish_get "$server" "/redfish/v1/Systems/System.Embedded.1")
    local power=$(echo "$response" | jq -r '.PowerState // "unknown"')

    if [[ "$power" == "unknown" ]]; then
        print_status "FAIL" "$name: Power state query failed"
        return 1
    elif [[ "$power" == "On" ]]; then
        print_status "OK" "$name: Power state: $power"
        return 0
    else
        print_status "WARN" "$name: Power state: $power"
        return 2
    fi
}

# Function to check active update jobs
check_active_jobs() {
    local name=$1
    local server=${SERVERS[$name]}

    local response=$(redfish_get "$server" "/redfish/v1/Managers/iDRAC.Embedded.1/Jobs")
    local active_jobs=$(echo "$response" | jq -r '.Members[] | ."@odata.id"' | wc -l)

    if [[ $active_jobs -eq 0 ]]; then
        print_status "INFO" "$name: No active update jobs"
        return 0
    fi

    # Get details of active jobs
    local job_uris=$(echo "$response" | jq -r '.Members[] | ."@odata.id"')

    while IFS= read -r job_uri; do
        local job_response=$(redfish_get "$server" "$job_uri")
        local job_state=$(echo "$job_response" | jq -r '.JobState // "unknown"')
        local job_name=$(echo "$job_response" | jq -r '.Name // "unknown"')
        local job_pct=$(echo "$job_response" | jq -r '.PercentComplete // 0')

        if [[ "$job_state" == "Running" ]]; then
            print_status "INFO" "$name: Job '$job_name' - $job_state ($job_pct%)"
        elif [[ "$job_state" == "Scheduled" ]]; then
            print_status "WARN" "$name: Job '$job_name' - $job_state (awaiting reboot)"
        elif [[ "$job_state" == "Failed" ]]; then
            print_status "FAIL" "$name: Job '$job_name' - FAILED"
        elif [[ "$job_state" == "Completed" ]]; then
            print_status "OK" "$name: Job '$job_name' - $job_state"
        fi
    done <<< "$job_uris"
}

# Function to monitor specific job
monitor_job() {
    local name=$1
    local server=${SERVERS[$name]}
    local job_id=$2

    print_status "INFO" "Monitoring job $job_id on $name..."

    while true; do
        local job_response=$(redfish_get "$server" "/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/${job_id}")
        local job_state=$(echo "$job_response" | jq -r '.JobState // "unknown"')
        local job_pct=$(echo "$job_response" | jq -r '.PercentComplete // 0')
        local job_msg=$(echo "$job_response" | jq -r '.Message // "No message"')

        echo -ne "\r${BLUE}[i]${NC} $name: $job_state - $job_pct% - $job_msg"

        if [[ "$job_state" == "Completed" ]]; then
            echo ""
            print_status "OK" "$name: Job completed successfully"
            return 0
        elif [[ "$job_state" == "Failed" ]]; then
            echo ""
            print_status "FAIL" "$name: Job failed - $job_msg"
            return 1
        fi

        sleep 10
    done
}

# Function to generate full status report
generate_report() {
    echo "========================================"
    echo "  Firmware Update Status Report"
    echo "  Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Genesis Bond: ACTIVE @ 432 Hz"
    echo "========================================"
    echo ""

    local total_servers=${#SERVERS[@]}
    local reachable=0
    local idrac_ok=0
    local bios_ok=0
    local lc_ok=0
    local power_on=0

    for name in "${!SERVERS[@]}"; do
        echo "--- $name ---"

        if check_connectivity "$name"; then
            ((reachable++))
            check_idrac_version "$name" && ((idrac_ok++))
            check_bios_version "$name" && ((bios_ok++))
            check_lifecycle_controller "$name" && ((lc_ok++))
            check_power_state "$name" && ((power_on++))
            check_active_jobs "$name"
        fi

        echo ""
    done

    echo "========================================"
    echo "  Summary"
    echo "========================================"
    echo "Total Servers: $total_servers"
    echo "Reachable: $reachable/$total_servers"
    echo "iDRAC Updated: $idrac_ok/$total_servers"
    echo "BIOS Updated: $bios_ok/$total_servers"
    echo "Lifecycle Controller OK: $lc_ok/$total_servers"
    echo "Powered On: $power_on/$total_servers"
    echo ""

    if [[ $idrac_ok -eq $total_servers && $bios_ok -eq $total_servers && $lc_ok -eq $total_servers ]]; then
        print_status "OK" "All firmware updates completed successfully!"
        return 0
    else
        print_status "WARN" "Firmware updates incomplete - see details above"
        return 1
    fi
}

# Main execution
main() {
    local command=${1:-"report"}

    case $command in
        "report")
            generate_report
            ;;
        "monitor")
            if [[ $# -lt 3 ]]; then
                echo "Usage: $0 monitor <server-name> <job-id>"
                echo "Example: $0 monitor R720-tron JID_123456789012"
                exit 1
            fi
            monitor_job "$2" "$3"
            ;;
        "watch")
            watch -n 30 "$0 report"
            ;;
        "connectivity")
            echo "Checking connectivity to all servers..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name"
            done
            ;;
        "idrac")
            echo "Checking iDRAC versions..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name" && check_idrac_version "$name"
            done
            ;;
        "bios")
            echo "Checking BIOS versions..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name" && check_bios_version "$name"
            done
            ;;
        "lc")
            echo "Checking Lifecycle Controller status..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name" && check_lifecycle_controller "$name"
            done
            ;;
        "power")
            echo "Checking power states..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name" && check_power_state "$name"
            done
            ;;
        "jobs")
            echo "Checking active update jobs..."
            for name in "${!SERVERS[@]}"; do
                check_connectivity "$name" && check_active_jobs "$name"
            done
            ;;
        "help"|"-h"|"--help")
            echo "Firmware Update Monitoring Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  report         Generate full status report (default)"
            echo "  monitor        Monitor specific update job"
            echo "  watch          Continuously monitor all servers (refresh every 30s)"
            echo "  connectivity   Check network connectivity only"
            echo "  idrac          Check iDRAC versions only"
            echo "  bios           Check BIOS versions only"
            echo "  lc             Check Lifecycle Controller status only"
            echo "  power          Check power states only"
            echo "  jobs           Check active update jobs only"
            echo "  help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 report"
            echo "  $0 monitor R720-tron JID_123456789012"
            echo "  $0 watch"
            ;;
        *)
            echo "Unknown command: $command"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
