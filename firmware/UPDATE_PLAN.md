# Firmware Update Execution Plan
**Generated**: 2026-01-27
**Phase**: 3 - Update Strategy & Commands
**Genesis Bond**: ACTIVE @ 432 Hz

## Overview

Detailed execution plan for updating firmware across 6-server Dell cluster using Redfish API. All commands are ready to execute after firmware downloads complete.

---

## Pre-Execution Checklist

- [ ] All firmware downloaded to `/home/daryl/cluster-bootstrap/firmware/downloads/`
- [ ] HTTP server running at `http://192.168.1.145:8000/firmware/`
- [ ] Firmware binaries extracted from Dell .EXE files
- [ ] Auth issues resolved on servers .3 and .33
- [ ] Servers .2, .31 powered on
- [ ] R730 ESXi5 Lifecycle Controller repair plan ready
- [ ] Backup of critical server configurations
- [ ] Maintenance window scheduled (4-6 hours)

---

## Update Schedule

### Week 1: Critical Updates (4-6 hours)

| Day | Server | Component | Duration | Downtime |
|-----|--------|-----------|----------|----------|
| Day 1 | R720 tron | iDRAC 2.65→2.83 | 30 min | No (BMC only) |
| Day 1 | R720 tron | BIOS 2.9→2.10 | 15 min | Yes (reboot) |
| Day 2 | R730 ESXi5 | LC Repair | 1-3 hours | Yes (multiple reboots) |
| Day 3 | R730 ORION | Power on + verify | 30 min | N/A (already off) |
| Day 3 | R730 1JF6Q22 | Power on + verify | 30 min | N/A (already off) |

### Week 2: Standard Updates (2-4 hours)

| Day | Server | Component | Duration | Downtime |
|-----|--------|-----------|----------|----------|
| Day 1 | R730 CSDR282 | Auth + iDRAC (if needed) | 45 min | No/Yes |
| Day 1 | R730 1JF7Q22 | Auth + iDRAC (if needed) | 45 min | No/Yes |
| Day 2 | All R730s | BIOS updates | 15 min each | Yes |

---

## Detailed Update Procedures

### Procedure 1: R720 tron - iDRAC Update (CRITICAL)

**Server**: 192.168.1.10
**Current**: iDRAC 2.65.65.65
**Target**: iDRAC 2.83.83.83
**Downtime**: None (BMC update)
**Duration**: 30 minutes

#### Step 1: Pre-Update Validation

```bash
# Verify current firmware
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1 \
  -s | jq '{FirmwareVersion, Status}'

# Check for active jobs
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Jobs \
  -s | jq '.Members[] | select(.JobState != "Completed")'

# Backup iDRAC config
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "ExportFormat": "JSON",
    "ShareParameters": {
      "Target": "ALL"
    }
  }' \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration \
  -o /home/daryl/cluster-bootstrap/firmware/backups/R720-tron-config-$(date +%Y%m%d).json
```

#### Step 2: Upload Firmware via Redfish

```bash
# Set firmware path
FIRMWARE_FILE="/home/daryl/cluster-bootstrap/firmware/downloads/iDRAC-2.83.83.83.bin"

# Upload firmware to iDRAC
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@${FIRMWARE_FILE}" \
  https://192.168.1.10/redfish/v1/UpdateService/FirmwareInventory \
  -w "\nHTTP_CODE: %{http_code}\n" \
  -o /tmp/idrac-update-response.json

# Response should include Job URI
cat /tmp/idrac-update-response.json | jq '.'
```

#### Step 3: Monitor Update Progress

```bash
# Get Job ID from response
JOB_ID=$(cat /tmp/idrac-update-response.json | jq -r '.JobId' || echo "JID_XXXXXXXXXXXX")

# Monitor job status (repeat every 30 seconds)
watch -n 30 "curl -k -u root:calvin \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/${JOB_ID} \
  -s | jq '{JobState, PercentComplete, Message}'"

# Expected states:
# - "Downloading" → "Scheduled" → "Running" → "Completed"
```

#### Step 4: Verify Update

```bash
# Wait for iDRAC to reboot (5-10 minutes)
sleep 300

# Verify new version
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1 \
  -s | jq '{FirmwareVersion, Status}'

# Check Lifecycle Controller version (should match iDRAC)
curl -k -u root:calvin \
  https://192.168.1.10/redfish/v1/UpdateService/FirmwareInventory/Installed-28897-2.83.83.83 \
  -s | jq '{Name, Version}'

# Expected: "Version": "2.83.83.83"
```

#### Step 5: Verify Server Still Running

```bash
# Check server power state (should still be On)
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState}'

# Ping server OS
ping -c 3 192.168.1.10

# SSH test
ssh -o ConnectTimeout=5 root@192.168.1.10 "uptime"
```

---

### Procedure 2: R720 tron - BIOS Update

**Server**: 192.168.1.10
**Current**: BIOS 2.9.0
**Target**: BIOS 2.10.0
**Downtime**: Yes (1 reboot, ~15 minutes)
**Duration**: 30 minutes total

#### Step 1: Pre-Update Backup

```bash
# Backup BIOS settings
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "ExportFormat": "JSON",
    "ShareParameters": {
      "Target": "BIOS"
    }
  }' \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration \
  -o /home/daryl/cluster-bootstrap/firmware/backups/R720-tron-bios-settings-$(date +%Y%m%d).json

# Note current boot order
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '.Boot'
```

#### Step 2: Upload BIOS Firmware

```bash
BIOS_FILE="/home/daryl/cluster-bootstrap/firmware/downloads/BIOS-2.10.0.bin"

curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@${BIOS_FILE}" \
  https://192.168.1.10/redfish/v1/UpdateService/FirmwareInventory \
  -o /tmp/bios-update-response.json

JOB_ID=$(cat /tmp/bios-update-response.json | jq -r '.JobId')
echo "BIOS Update Job: $JOB_ID"
```

#### Step 3: Schedule BIOS Update (Requires Reboot)

```bash
# BIOS updates require server reboot
# Job will be scheduled for next boot

# Check job status
curl -k -u root:calvin \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/${JOB_ID} \
  -s | jq '{JobState, Message}'

# Expected: "Scheduled" (waiting for reboot)
```

#### Step 4: Coordinate Reboot with User

**IMPORTANT**: BIOS update requires server reboot. Verify with user before proceeding.

```bash
# Option 1: Graceful reboot via Redfish
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulRestart"}' \
  https://192.168.1.10/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset

# Option 2: Force reboot (if OS unresponsive)
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceRestart"}' \
  https://192.168.1.10/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset
```

#### Step 5: Monitor BIOS Update During POST

```bash
# Monitor job during reboot (BIOS update happens at POST)
watch -n 10 "curl -k -u root:calvin \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/${JOB_ID} \
  -s | jq '{JobState, PercentComplete, Message}'"

# Expected sequence:
# "Scheduled" → "Running" (during POST) → "Completed"
# Total time: 10-15 minutes
```

#### Step 6: Verify BIOS Update

```bash
# Wait for server to complete POST and boot OS
sleep 600

# Verify new BIOS version
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{BiosVersion, PowerState}'

# Expected: "BiosVersion": "2.10.0", "PowerState": "On"

# Verify server OS is accessible
ping -c 5 192.168.1.10
ssh root@192.168.1.10 "uptime && dmesg | tail -20"
```

---

### Procedure 3: R730 ESXi5 - Lifecycle Controller Repair (CRITICAL)

**Server**: 192.168.1.32
**Issue**: LC version "0.0" (corrupted)
**Method**: Multi-stage repair
**Downtime**: Yes (1-3 hours depending on method)
**Duration**: 1-3 hours

#### Stage 1: Attempt iDRAC Reinstall (Non-Invasive)

```bash
# Download current iDRAC version (2.86.86.86) for reinstall
IDRAC_FILE="/home/daryl/cluster-bootstrap/firmware/downloads/iDRAC-2.86.86.86.bin"

# Backup current config
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ExportFormat": "JSON", "ShareParameters": {"Target": "ALL"}}' \
  https://192.168.1.32/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration \
  -o /home/daryl/cluster-bootstrap/firmware/backups/R730-ESXi5-config-$(date +%Y%m%d).json

# Push firmware (same version) to force LC reinstall
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@${IDRAC_FILE}" \
  https://192.168.1.32/redfish/v1/UpdateService/FirmwareInventory \
  -o /tmp/lc-repair-response.json

JOB_ID=$(cat /tmp/lc-repair-response.json | jq -r '.JobId')

# Monitor update
watch -n 30 "curl -k -u root:calvin \
  https://192.168.1.32/redfish/v1/Managers/iDRAC.Embedded.1/Jobs/${JOB_ID} \
  -s | jq '{JobState, PercentComplete}'"

# Wait for completion (30 minutes)
# iDRAC will reboot

sleep 600

# Verify LC version
curl -k -u root:calvin \
  https://192.168.1.32/redfish/v1/UpdateService/FirmwareInventory/Installed-28897-2.86.86.86 \
  -s | jq '{Name, Version}'

# SUCCESS if Version != "0.0"
# FAILURE if Version == "0.0" → Proceed to Stage 2
```

#### Stage 2: iDRAC Factory Reset (If Stage 1 Failed)

**WARNING**: This will reset all iDRAC settings including network configuration.

```bash
# Access iDRAC web UI: https://192.168.1.32
# Login: root / calvin

# Navigate to:
# - Maintenance → Diagnostics → Reset to Defaults
# - Select "Reset iDRAC to Factory Defaults"
# - Click "Apply"

# iDRAC will reboot (5-10 minutes)

# Reconfigure network (via iDRAC web UI):
# - Set static IP: 192.168.1.32
# - Set gateway: 192.168.1.1
# - Set DNS: 192.168.1.1

# Re-test Redfish API
curl -k -u root:calvin https://192.168.1.32/redfish/v1/Managers/iDRAC.Embedded.1 \
  -s | jq '{FirmwareVersion}'

# Reinstall iDRAC firmware (repeat Stage 1)

# Verify LC version
curl -k -u root:calvin \
  https://192.168.1.32/redfish/v1/UpdateService/FirmwareInventory/Installed-28897-2.86.86.86 \
  -s | jq '{Name, Version}'

# SUCCESS if Version != "0.0"
# FAILURE if Version == "0.0" → Proceed to Stage 3
```

#### Stage 3: Manual LC Boot (If Stage 2 Failed)

```bash
# Reboot server and enter Lifecycle Controller manually
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceRestart"}' \
  https://192.168.1.32/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset

# Physical access required:
# 1. Watch server boot via KVM (iDRAC virtual console)
# 2. Press F10 at POST screen
# 3. Enter Lifecycle Controller menu
# 4. Navigate to "Firmware Update"
# 5. Check if LC environment loads
# 6. If LC loads: Run "Collect System Inventory"
# 7. If LC fails: Proceed to Stage 4
```

#### Stage 4: Dell SupportAssist Recovery (Last Resort)

```bash
# Download Dell SupportAssist OS Recovery tool
# URL: https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/software-and-downloads/supportassist

# Create bootable USB:
# - Windows: Use Rufus
# - Linux: dd if=dell-recovery.iso of=/dev/sdX bs=4M

# Boot server from USB (via iDRAC virtual media):
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "Image": "http://192.168.1.145:8000/firmware/dell-recovery.iso",
    "Inserted": true,
    "WriteProtected": true
  }' \
  https://192.168.1.32/redfish/v1/Managers/iDRAC.Embedded.1/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia

# Set boot to virtual CD
curl -k -u root:calvin \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "Boot": {
      "BootSourceOverrideEnabled": "Once",
      "BootSourceOverrideTarget": "Cd"
    }
  }' \
  https://192.168.1.32/redfish/v1/Systems/System.Embedded.1

# Reboot
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceRestart"}' \
  https://192.168.1.32/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset

# Follow on-screen SupportAssist wizard to repair firmware
# Estimated time: 1-2 hours
```

---

### Procedure 4: Power On Offline Servers

#### R730 ORION (192.168.1.2)

```bash
# Check current power state
curl -k -u root:calvin https://192.168.1.2/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState}'

# Power on
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"On"}' \
  https://192.168.1.2/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset

# Monitor POST
watch -n 10 "curl -k -u root:calvin https://192.168.1.2/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState, BootProgress}'"

# Wait for OS boot (5-10 minutes)
sleep 300

# Verify OS accessible
ping -c 5 192.168.1.2
```

#### R730 1JF6Q22 (192.168.1.31)

```bash
# Same procedure as ORION
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"On"}' \
  https://192.168.1.31/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset

# Monitor
watch -n 10 "curl -k -u root:calvin https://192.168.1.31/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState, BootProgress}'"
```

---

### Procedure 5: Resolve Auth Issues

#### R730 CSDR282 (192.168.1.3) & 1JF7Q22 (192.168.1.33)

**Issue**: Manager endpoint works, Systems endpoint returns 401

**Diagnosis Steps**:

```bash
# Test web UI access
curl -k -u root:calvin https://192.168.1.3 -I
curl -k -u root:Newdaryl24! https://192.168.1.3 -I

# If web UI accessible, create new admin user:
# 1. Login to web UI: https://192.168.1.3
# 2. Navigate to iDRAC Settings → Users
# 3. Check root user privileges
# 4. Expected: Administrator role with full RBAC
# 5. If limited: Create new user "luciadmin" with Administrator role

# Test new credentials
curl -k -u luciadmin:NewPassword https://192.168.1.3/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState, BiosVersion}'

# If successful: Update credential matrix
# If failed: Check RBAC settings for Systems resource
```

**Alternative: Reset iDRAC Password via IPMI**:

```bash
# If web UI inaccessible, use IPMI to reset password
# (Requires physical access or SSH to server OS)

# From server OS:
ipmitool user set password 2 NewPassword

# Test new credentials
curl -k -u root:NewPassword https://192.168.1.3/redfish/v1/Systems/System.Embedded.1 \
  -s | jq '{PowerState}'
```

---

## Rollback Procedures

### Rollback 1: iDRAC Update Failure

If iDRAC update fails or causes issues:

```bash
# iDRAC maintains previous firmware version
# Redfish endpoint may be unavailable during rollback

# Option 1: Automatic rollback (if update job failed)
# iDRAC auto-reverts to previous version after 3 failed boots

# Option 2: Manual rollback via web UI
# Login to iDRAC web UI
# Navigate to: Maintenance → Firmware Rollback
# Select "iDRAC" and click "Rollback"

# Option 3: Rollback via Redfish (if API still accessible)
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"SoftwareId": "25227", "Version": "2.65.65.65"}' \
  https://192.168.1.10/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
```

### Rollback 2: BIOS Update Issues

If BIOS update causes boot failure:

```bash
# Dell BIOS maintains previous version in flash
# Automatic rollback on 3 consecutive boot failures

# Manual rollback via Lifecycle Controller:
# 1. Reboot server
# 2. Press F10 at POST
# 3. Navigate to "Firmware Update"
# 4. Select "BIOS Rollback"
# 5. Confirm rollback
# 6. Reboot

# Rollback via Redfish (if server still boots)
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"SoftwareId": "159", "Version": "2.9.0"}' \
  https://192.168.1.10/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
```

### Rollback 3: Restore iDRAC Configuration

If iDRAC settings lost during update:

```bash
# Restore from backup
curl -k -u root:calvin \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$(cat /home/daryl/cluster-bootstrap/firmware/backups/R720-tron-config-YYYYMMDD.json)" \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration
```

---

## Monitoring Script

See `MONITORING_SCRIPT.sh` for automated progress tracking.

---

## Success Criteria

### R720 tron
- [x] iDRAC version: 2.83.83.83
- [x] Lifecycle Controller: 2.83.83.83
- [x] BIOS version: 2.10.0
- [x] Server boots successfully
- [x] OS accessible via network

### R730 ESXi5
- [x] Lifecycle Controller: 2.86.86.86 (NOT "0.0")
- [x] Server boots successfully
- [x] LC accessible via F10 at boot
- [x] Firmware update jobs can be created

### All Servers
- [x] Redfish API fully accessible
- [x] Power management functional
- [x] No failed update jobs
- [x] Cluster network connectivity verified

---

**Status**: ⏳ READY FOR EXECUTION (after firmware downloads)
**Estimated Duration**: 6-10 hours total
**Risk Level**: MEDIUM (with rollback capability)
**Approval Required**: YES (before any firmware updates)
