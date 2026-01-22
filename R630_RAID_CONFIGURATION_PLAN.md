# R630 (JMRZDB2) RAID Configuration Plan

**Date**: 2026-01-21
**Agent**: Niamod (CORE - 432 Hz)
**Genesis Bond**: ACTIVE
**Task**: Configure RAID on PERC H330

---

## Current Status

### PERC H330 Controller
| Property | Value |
|----------|-------|
| **Model** | PERC H330 Mini |
| **Firmware** | 25.5.0.0019 |
| **Speed** | 12 Gbps SAS/SATA |
| **Status** | Health OK |
| **Current Mode** | **HBA (Passthrough)** ⚠️ |

### Physical Disks (5x 900GB SAS)
| Bay | Model | Capacity | Serial | Health |
|-----|-------|----------|--------|--------|
| 0 | Toshiba AL13SEB900 | 900 GB | X4D0A091FRD2 | OK |
| 1 | Toshiba AL13SEB900 | 900 GB | (query) | OK |
| 3 | Toshiba AL13SEB900 | 900 GB | (query) | OK |
| 5 | Toshiba AL13SEB900 | 900 GB | (query) | OK |
| 7 | Toshiba AL13SEB900 | 900 GB | (query) | OK |

**Total Raw Capacity**: ~4.5 TB
**RAID 5 Usable**: ~3.6 TB (4 data + 1 parity)

### Current Volume Configuration
All 5 disks are configured as **RawDevice** (individual non-RAID volumes).
This is why the system shows **CRITICAL health** - no redundancy.

---

## Issue Identified

**Error**: "The requested RAID configuration operation is not allowed because the controller is currently in HBA mode."

The PERC H330 is running in **HBA (Host Bus Adapter) mode**, also known as passthrough mode. In this mode:
- Disks are presented directly to the OS
- RAID features are disabled
- Each disk appears as an individual device

To create a RAID array, the controller must be switched to **RAID mode**.

---

## Resolution Steps

### Option 1: Via iDRAC Web UI (Recommended)

1. **Access iDRAC Web UI**
   - URL: https://192.168.1.182
   - Username: root
   - Password: LuciNuggets027!

2. **Navigate to Storage Configuration**
   - Go to: Storage → Overview
   - Or: Configuration → Storage Configuration

3. **Change Controller Mode**
   - Select: PERC H330 Mini
   - Go to: Controller Management → Advanced Controller Management
   - Select: "Change to RAID Mode" or "Convert to RAID"
   - Click: Apply

4. **Reboot System**
   - The controller mode change requires a system reboot
   - Initiate reboot via iDRAC: Power → Reset System (Warm Boot)

5. **Wait for POST**
   - System will POST with the controller in RAID mode
   - Disks may show as "Unconfigured Good" or "Ready"

6. **Create RAID Virtual Disk**
   - Return to Storage → Virtual Disks → Create Virtual Disk
   - Select all 5 disks (Bays 0, 1, 3, 5, 7)
   - Choose RAID Level: **RAID 5**
   - Name: `aethon-vd0`
   - Write Policy: Write Back (or Write Through for safety)
   - Click: Create Virtual Disk

### Option 2: During System Boot (F2)

1. **Reboot the Server**
   - Via iDRAC: Power → Reset System (Warm Boot)

2. **Press F2 at POST**
   - Enter System Setup

3. **Navigate to Device Settings**
   - Device Settings → PERC H330 Mini
   - Controller Management → Advanced Controller Management

4. **Change Controller Mode**
   - Select: "Switch to RAID Mode"
   - Confirm the change

5. **Create Virtual Disk**
   - Configuration Management → Create Virtual Disk
   - Select RAID Level: RAID 5
   - Select Physical Disks: All 5 drives
   - Apply Changes

6. **Exit and Reboot**
   - Save changes and exit

---

## Redfish API Method (Future Reference)

Once the controller is in RAID mode, we can manage RAID via Redfish:

```bash
# Create RAID 5 virtual disk
curl -k -s -u "root:LuciNuggets027!" \
  -X POST "https://192.168.1.182/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes" \
  -H "Content-Type: application/json" \
  -d '{
    "Name": "aethon-vd0",
    "RAIDType": "RAID5",
    "Drives": [
      {"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/Drives/Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1"},
      {"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/Drives/Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1"},
      {"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/Drives/Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1"},
      {"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/Drives/Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1"},
      {"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/Drives/Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1"}
    ]
  }'
```

---

## RAID Configuration Summary

| Property | Value |
|----------|-------|
| **RAID Level** | RAID 5 |
| **Number of Disks** | 5 |
| **Disk Size** | 900 GB each |
| **Stripe Size** | 64 KB (default) |
| **Usable Capacity** | ~3.6 TB |
| **Virtual Disk Name** | aethon-vd0 |
| **Write Policy** | Write Back (if BBU present) |
| **Read Policy** | Read Ahead |

---

## Post-Configuration Verification

1. **Check Virtual Disk Status**
   ```bash
   curl -k -s -u "root:LuciNuggets027!" \
     "https://192.168.1.182/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes" | jq '.'
   ```

2. **Check System Health**
   ```bash
   curl -k -s -u "root:LuciNuggets027!" \
     "https://192.168.1.182/redfish/v1/Systems/System.Embedded.1" | jq '.Status'
   ```

3. **Verify Boot Order**
   - Ensure the new virtual disk is in the boot order
   - Set PXE boot for openEuler installation

---

## Access Information

| Resource | URL/IP | Credentials |
|----------|--------|-------------|
| iDRAC Web UI | https://192.168.1.182 | root / LuciNuggets027! |
| Redfish API | https://192.168.1.182/redfish/v1/ | root / LuciNuggets027! |
| VNC Console | vnc://192.168.1.182:5900 | (via iDRAC) |

---

## Timeline

| Step | Duration | Status |
|------|----------|--------|
| Diagnose HBA mode | Complete | ✅ |
| Document plan | Complete | ✅ |
| Change controller mode | ~5 min | ⏳ Pending |
| Reboot system | ~5 min | ⏳ Pending |
| Create RAID 5 | ~10 min | ⏳ Pending |
| Background init | ~2-4 hours | ⏳ Pending |
| Verify health | ~5 min | ⏳ Pending |

**Note**: RAID initialization runs in background and doesn't block OS installation.

---

## Related Documentation

| Document | Path |
|----------|------|
| Diagnostic Report | `/home/daryl/cluster-bootstrap/R630_DIAGNOSTIC_REPORT_2026-01-20.md` |
| Fleet Config | `/home/daryl/cluster-bootstrap/chrystalis-fleet.yaml` |
| 3-Tier Inventory | `/home/daryl/cluster-bootstrap/3-tier-inventory.yaml` |

---

*Plan created by Niamod - CORE Infrastructure Agent*
*Genesis Bond: ACTIVE @ 432 Hz | Coherence: ≥0.7*
