# Redfish API Discovery Report
**Generated**: 2026-01-27
**Phase**: 1 - Complete
**Genesis Bond**: ACTIVE @ 432 Hz (CORE Tier - Infrastructure)

## Executive Summary

Successfully connected to **4 of 6 servers** via Redfish API. Two servers (.3, .33) have authentication issues requiring investigation.

### Critical Findings
1. **R730 ESXi5 Lifecycle Controller FAILURE**: Version reports "0.0" (Updateable: false)
2. **R720 tron**: Ancient firmware (iDRAC 2.65.65.65) - CRITICAL UPDATE NEEDED
3. **Auth Issue**: Servers .3 and .33 reject `Newdaryl24!` password for Systems endpoint

---

## Server Inventory with Redfish Capabilities

### Server 1: R720 tron (192.168.1.10) - CRITICAL PRIORITY

| Property | Value |
|----------|-------|
| **Service Tag** | 4J0TV12 |
| **Model** | PowerEdge R720 (12G Monolithic) |
| **Power State** | On |
| **Credentials** | root:calvin ✓ |
| **iDRAC Version** | 2.65.65.65 ⚠️ ANCIENT |
| **Lifecycle Controller** | 2.65.65.65 (Updateable: false) |
| **BIOS Version** | 2.9.0 |
| **Memory** | 536.44 GB |
| **Redfish Endpoint** | /redfish/v1 (working) |
| **Update Method** | HttpPushUri: /redfish/v1/UpdateService/FirmwareInventory |

**Firmware Issues**:
- iDRAC 2.65.65.65 is from ~2019 (latest is 2.83+)
- Lifecycle Controller tied to iDRAC version
- BIOS 2.9.0 may need update to 2.10.x

**Update Priority**: ⚠️ **CRITICAL** - iDRAC first, then BIOS

---

### Server 2: R730 ORION (192.168.1.2) - HIGH PRIORITY

| Property | Value |
|----------|-------|
| **Service Tag** | CQ5QBM2 |
| **Model** | PowerEdge R730 (13G Monolithic) |
| **Power State** | Off ⏸️ |
| **Credentials** | root:calvin ✓ |
| **iDRAC Version** | 2.86.86.86 |
| **BIOS Version** | 2.19.0 |
| **Memory** | 384 GB |
| **Redfish Endpoint** | /redfish/v1 (working) |
| **Update Method** | HttpPushUri: /redfish/v1/UpdateService/FirmwareInventory |

**Action Required**:
1. Power on server (Redfish power control available)
2. Check if iDRAC 2.86 is latest for R730
3. BIOS 2.19.0 likely current

**Update Priority**: HIGH - Power on for cluster integration

---

### Server 3: R730 ESXi5 (192.168.1.32) - CRITICAL INVESTIGATION

| Property | Value |
|----------|-------|
| **Service Tag** | 1JD8Q22 |
| **Model** | PowerEdge R730 (13G Monolithic) |
| **Power State** | On |
| **Credentials** | root:calvin ✓ |
| **iDRAC Version** | 2.86.86.86 |
| **Lifecycle Controller** | 0.0 ❌ CORRUPTED |
| **BIOS Version** | 2.19.0 |
| **Memory** | 384 GB |
| **Redfish Endpoint** | /redfish/v1 (working) |
| **Update Method** | HttpPushUri available, but LC broken |

**Critical Issue**:
```json
{
  "Name": "Lifecycle Controller",
  "Version": "0.0",
  "SoftwareId": "28897",
  "Updateable": false,
  "ReleaseDate": null
}
```

**Diagnosis**:
- Lifecycle Controller shows version "0.0" (invalid)
- Marked as "Updateable: false" (cannot update via normal methods)
- iDRAC 2.86.86.86 is functional, but LC component is corrupted

**Recovery Options**:
1. **iDRAC Factory Reset** - May restore LC to functional state
2. **Boot to Lifecycle Controller** - F10 at boot, check if accessible
3. **iDRAC Reinstall** - Push iDRAC firmware again (may repair LC)
4. **Dell SupportAssist OS Recovery** - Last resort bootable media

**Update Priority**: ⚠️ **CRITICAL** - LC repair required before any firmware updates

---

### Server 4: R730 CSDR282 (192.168.1.3) - AUTH ISSUE

| Property | Value |
|----------|-------|
| **Service Tag** | CSDR282 |
| **Model** | PowerEdge R730 (13G Monolithic) |
| **Power State** | Unknown (auth failed) |
| **Credentials** | root:calvin ❌ / root:Newdaryl24! ⚠️ Partial |
| **iDRAC Version** | 2.86.86.86 (from Manager endpoint) |
| **BIOS Version** | Unknown (Systems endpoint auth failed) |
| **Redfish Endpoint** | /redfish/v1/Managers working, /redfish/v1/Systems 401 |

**Auth Issue**:
- `/redfish/v1/Managers/iDRAC.Embedded.1` works with `Newdaryl24!`
- `/redfish/v1/Systems/System.Embedded.1` returns 401 Unauthorized
- Possible RBAC misconfiguration or privilege escalation needed

**Investigation Steps**:
1. Check iDRAC user privileges via web UI (https://192.168.1.3)
2. Test with Administrator role account
3. Review iDRAC RBAC settings for Systems resource access

**Update Priority**: MEDIUM - Auth issue must be resolved first

---

### Server 5: R730 1JF6Q22 (192.168.1.31) - OFFLINE

| Property | Value |
|----------|-------|
| **Service Tag** | 1JF6Q22 |
| **Model** | PowerEdge R730 (13G Monolithic) |
| **Power State** | Off ⏸️ |
| **Credentials** | root:calvin ✓ |
| **iDRAC Version** | 2.86.86.86 |
| **BIOS Version** | 2.19.0 |
| **Memory** | 384 GB |
| **Redfish Endpoint** | /redfish/v1 (working) |
| **Update Method** | HttpPushUri: /redfish/v1/UpdateService/FirmwareInventory |

**Action Required**: Power on via Redfish before firmware updates

**Update Priority**: MEDIUM - Standard R730 maintenance

---

### Server 6: R730 1JF7Q22 (192.168.1.33) - AUTH ISSUE

| Property | Value |
|----------|-------|
| **Service Tag** | 1JF7Q22 |
| **Model** | PowerEdge R730 (13G Monolithic) |
| **Power State** | Unknown (auth failed) |
| **Credentials** | root:calvin ❌ / root:Newdaryl24! ⚠️ Partial |
| **iDRAC Version** | 2.86.86.86 (from Manager endpoint) |
| **BIOS Version** | Unknown (Systems endpoint auth failed) |
| **Redfish Endpoint** | /redfish/v1/Managers working, /redfish/v1/Systems 401 |

**Auth Issue**: Same as CSDR282 - Manager endpoint works, Systems endpoint fails

**Update Priority**: MEDIUM - Auth issue must be resolved first

---

## Credential Matrix

| Server | IP | root:calvin | root:Newdaryl24! | Notes |
|--------|-----|-------------|------------------|-------|
| R720 tron | 192.168.1.10 | ✓ Full | Not tested | Default creds working |
| R730 ORION | 192.168.1.2 | ✓ Full | Not tested | Default creds working |
| R730 ESXi5 | 192.168.1.32 | ✓ Full | Not tested | Default creds working |
| R730 CSDR282 | 192.168.1.3 | ❌ | ⚠️ Manager only | RBAC issue |
| R730 1JF6Q22 | 192.168.1.31 | ✓ Full | Not tested | Default creds working |
| R730 1JF7Q22 | 192.168.1.33 | ❌ | ⚠️ Manager only | RBAC issue |

---

## Redfish Update Capabilities

All servers support **HTTP Push URI** update method:
```
POST /redfish/v1/UpdateService/FirmwareInventory
Content-Type: application/octet-stream
Body: <firmware binary>
```

### Update Workflow
1. Download firmware .exe from Dell Support
2. Extract firmware binary (Dell .exe contains embedded DUP)
3. POST binary to Redfish endpoint
4. Monitor job status via `/redfish/v1/Managers/iDRAC.Embedded.1/Jobs`
5. Reboot server to apply (if required)

### Limitations
- **Lifecycle Controller required** for firmware staging
- **Server must be powered on** (or iDRAC can power it on)
- **No MultipartHttpPushUri** support on these iDRAC versions

---

## Critical Issues Summary

### Issue 1: R730 ESXi5 Lifecycle Controller Corruption ⚠️
**Impact**: Cannot update any firmware (BIOS, NICs, RAID, etc.)
**Root Cause**: LC version reports "0.0", marked non-updateable
**Resolution Path**:
1. Attempt iDRAC firmware reinstall (may repair LC)
2. If failed, iDRAC factory reset
3. If failed, Dell SupportAssist bootable media
4. Worst case: Manual LC reinstall via boot menu

### Issue 2: R720 Ancient Firmware ⚠️
**Impact**: Security vulnerabilities, missing features
**Root Cause**: iDRAC 2.65.65.65 from ~2019 (7 years old)
**Resolution Path**:
1. Update iDRAC to 2.83+ (latest for R720)
2. LC will auto-update with iDRAC
3. Update BIOS to 2.10.x
4. Update NICs, RAID firmware

### Issue 3: RBAC Auth Failure on 2 Servers
**Impact**: Cannot query power state, BIOS, or perform updates
**Root Cause**: Manager endpoint works, Systems endpoint 401
**Resolution Path**:
1. Check iDRAC user privileges via web UI
2. Create new Administrator account
3. Investigate RBAC configuration
4. May need password reset via web UI

---

## Next Steps (Phase 2: Firmware Preparation)

1. **Download Required Firmware**:
   - R720: iDRAC 2.83+ (SoftwareId: 25227)
   - R720: BIOS 2.10.x (SoftwareId: 159)
   - R730: Check if iDRAC 2.86 is latest (may be 2.90+)
   - R730: BIOS updates if newer than 2.19.0

2. **Resolve Auth Issues**:
   - Test web UI access to .3 and .33
   - Create Administrator accounts with full RBAC
   - Document working credentials

3. **Power Management**:
   - Power on servers .2, .31 via Redfish
   - Verify all servers responsive before updates

4. **LC Repair Plan**:
   - Document iDRAC reinstall procedure for .32
   - Prepare Dell SupportAssist ISO as backup
   - Test LC accessibility via F10 boot menu

---

## Firmware Inventory URLs

### Dell Support Portal
- R720 (Service Tag: 4J0TV12): https://www.dell.com/support/home/product-support/servicetag/4J0TV12
- R730 ORION (CQ5QBM2): https://www.dell.com/support/home/product-support/servicetag/CQ5QBM2
- R730 ESXi5 (1JD8Q22): https://www.dell.com/support/home/product-support/servicetag/1JD8Q22
- R730 CSDR282: https://www.dell.com/support/home/product-support/servicetag/CSDR282
- R730 1JF6Q22: https://www.dell.com/support/home/product-support/servicetag/1JF6Q22
- R730 1JF7Q22: https://www.dell.com/support/home/product-support/servicetag/1JF7Q22

### Direct Firmware Links (To Be Populated)
Links will be documented in `FIRMWARE_MANIFEST.md` after manual download verification.

---

**Discovery Phase**: ✅ COMPLETE
**Servers Accessible**: 4/6 (67%)
**Critical Issues**: 3 (LC corruption, ancient firmware, auth failures)
**Ready for Phase 2**: Yes (with auth resolution)
