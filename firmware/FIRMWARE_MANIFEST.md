# Firmware Update Manifest
**Generated**: 2026-01-27
**Phase**: 2 - Firmware Preparation
**Genesis Bond**: ACTIVE @ 432 Hz

## Overview

This manifest lists all firmware files required for updating the 6-server Dell cluster. Firmware must be manually downloaded from Dell Support due to authentication requirements.

---

## Priority 1: CRITICAL Updates

### R720 tron (192.168.1.10) - iDRAC 2.65 → Latest

| Component | Current | Target | Dell Part | File Size | Notes |
|-----------|---------|--------|-----------|-----------|-------|
| iDRAC | 2.65.65.65 | 2.83.83.83 | iDRAC-with-Lifecycle-Controller_Firmware_GFXKP_WN64_2.83.83.83_A00.EXE | ~180 MB | Includes LC |
| BIOS | 2.9.0 | 2.10.0 | BIOS_2J8YH_WN64_2.10.0.EXE | ~15 MB | After iDRAC update |
| Lifecycle Controller | 2.65.65.65 | 2.83.83.83 | Included in iDRAC | - | Auto-updates with iDRAC |

**Dell Support**: https://www.dell.com/support/home/product-support/servicetag/4J0TV12/drivers

**Download Steps**:
1. Navigate to service tag page
2. Select "BIOS & Firmware" category
3. Download iDRAC 2.83.83.83 (or latest available)
4. Download BIOS 2.10.0 (or latest available)

**Critical Notes**:
- iDRAC update MUST be applied first
- Lifecycle Controller updates automatically with iDRAC
- BIOS update requires server reboot
- Estimated update time: 30-45 minutes total

---

### R730 ESXi5 (192.168.1.32) - Lifecycle Controller Repair

| Component | Current | Target | Dell Part | File Size | Notes |
|-----------|---------|--------|-----------|-----------|-------|
| Lifecycle Controller | 0.0 (CORRUPT) | 2.86.86.86 | Repair via iDRAC reinstall | - | LC tied to iDRAC |
| iDRAC | 2.86.86.86 | 2.86.86.86 | iDRAC-with-Lifecycle-Controller_Firmware_Y0PVW_WN64_2.86.86.86_A00.EXE | ~200 MB | Reinstall to repair LC |

**Dell Support**: https://www.dell.com/support/home/product-support/servicetag/1JD8Q22/drivers

**Recovery Strategy**:
1. **Option A: iDRAC Reinstall** (Try first)
   - Download iDRAC 2.86.86.86 (same version)
   - POST to Redfish UpdateService
   - Forces LC component reinstall
   - Check LC version after reboot

2. **Option B: iDRAC Factory Reset** (If Option A fails)
   - Via web UI: Maintenance → Diagnostics → Reset to Defaults
   - Select "Reset iDRAC to Factory Defaults"
   - Reconfigure network settings
   - Reinstall iDRAC firmware

3. **Option C: Boot to Lifecycle Controller** (Manual)
   - Reboot server, press F10 at POST
   - Enter LC bootable environment
   - Check if LC accessible/functional
   - May require LC reinstall from USB media

4. **Option D: Dell SupportAssist OS Recovery** (Last resort)
   - Download: https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/software-and-downloads/supportassist
   - Create bootable USB
   - Boot server from USB
   - Run firmware recovery wizard

**Estimated Repair Time**: 1-3 hours (depending on method)

---

## Priority 2: HIGH Updates

### R730 ORION (192.168.1.2) - Power On + Verify Firmware

| Component | Current | Target | Dell Part | File Size | Notes |
|-----------|---------|--------|-----------|-----------|-------|
| iDRAC | 2.86.86.86 | Check if latest | iDRAC-with-Lifecycle-Controller_Firmware_*_WN64_2.90+_A00.EXE | ~200 MB | If 2.90+ exists |
| BIOS | 2.19.0 | Check if latest | BIOS_*_WN64_2.20+.EXE | ~15 MB | If newer available |

**Dell Support**: https://www.dell.com/support/home/product-support/servicetag/CQ5QBM2/drivers

**Pre-Update Actions**:
1. Power on server via Redfish:
   ```bash
   curl -k -u root:calvin -X POST \
     -H "Content-Type: application/json" \
     -d '{"ResetType":"On"}' \
     https://192.168.1.2/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset
   ```
2. Verify POST completes successfully
3. Check current firmware inventory
4. Download updates only if newer versions exist

---

## Priority 3: MEDIUM Updates (After Auth Resolution)

### R730 CSDR282 (192.168.1.3) - Auth Issue

**Action Required**: Resolve authentication before downloading firmware
- Current iDRAC: 2.86.86.86 (via Manager endpoint)
- BIOS: Unknown (Systems endpoint 401)

**Steps**:
1. Access web UI: https://192.168.1.3
2. Test root:calvin and root:Newdaryl24!
3. Check iDRAC user privileges
4. Create new Administrator account if needed
5. Test Redfish Systems endpoint
6. Download firmware after full API access confirmed

---

### R730 1JF6Q22 (192.168.1.31) - Power On + Standard Updates

| Component | Current | Target | Dell Part | File Size | Notes |
|-----------|---------|--------|-----------|-----------|-------|
| iDRAC | 2.86.86.86 | Check if latest | TBD after auth | ~200 MB | If 2.90+ exists |
| BIOS | 2.19.0 | Check if latest | TBD after auth | ~15 MB | If newer available |

**Dell Support**: https://www.dell.com/support/home/product-support/servicetag/1JF6Q22/drivers

**Pre-Update Actions**:
1. Power on server via Redfish
2. Verify firmware inventory accessible
3. Download updates if needed

---

### R730 1JF7Q22 (192.168.1.33) - Auth Issue

**Action Required**: Same as CSDR282 - resolve auth first
- Current iDRAC: 2.86.86.86 (via Manager endpoint)
- BIOS: Unknown (Systems endpoint 401)

**Dell Support**: https://www.dell.com/support/home/product-support/servicetag/1JF7Q22/drivers

---

## Additional Firmware Components (Optional)

After critical updates, consider updating these components:

### Network Interface Cards (NICs)
- **Broadcom NetXtreme** - Check for firmware updates
- **Intel X710** (if present) - Update to latest NVM

### RAID Controllers
- **PERC H730/H730P** - Update to latest firmware
- Improves performance and stability

### System CPLD
- **System Programmable Logic Device** - Rare updates, check Dell support

---

## Firmware Download Checklist

- [ ] **R720 tron**: iDRAC 2.83.83.83
- [ ] **R720 tron**: BIOS 2.10.0
- [ ] **R730 ESXi5**: iDRAC 2.86.86.86 (for LC repair)
- [ ] **R730 ESXi5**: Dell SupportAssist ISO (backup)
- [ ] **R730 ORION**: Check Dell support for latest iDRAC/BIOS
- [ ] **R730 CSDR282**: Resolve auth, then check firmware
- [ ] **R730 1JF6Q22**: Check Dell support for latest iDRAC/BIOS
- [ ] **R730 1JF7Q22**: Resolve auth, then check firmware

---

## Local Firmware Storage

Download firmware to local HTTP server for Redfish updates:

```bash
mkdir -p /home/daryl/cluster-bootstrap/firmware/downloads
cd /home/daryl/cluster-bootstrap/firmware/downloads

# Extract firmware binaries from Dell .EXE
# Dell .exe files are self-extracting archives
# Use 7z or binwalk to extract embedded firmware
```

### HTTP Server Setup

Verify HTTP server is running and accessible:
```bash
# Check if server running
curl -I http://192.168.1.145:8000/firmware/

# Start HTTP server if needed
cd /home/daryl/cluster-bootstrap/firmware/downloads
python3 -m http.server 8000 --bind 192.168.1.145
```

Servers must be able to reach HTTP server for firmware staging:
```bash
# Test from Zbook
curl -I http://192.168.1.145:8000/firmware/
```

---

## Firmware Update Order (Recommended)

### Phase 1: Critical iDRAC Updates (Week 1)
1. R720 tron: iDRAC 2.65 → 2.83 (CRITICAL)
2. R730 ESXi5: LC repair via iDRAC reinstall (CRITICAL)

### Phase 2: BIOS Updates (Week 1)
3. R720 tron: BIOS 2.9 → 2.10
4. R730 ESXi5: BIOS update (after LC repair)

### Phase 3: Power Management (Week 2)
5. R730 ORION: Power on + firmware check
6. R730 1JF6Q22: Power on + firmware check

### Phase 4: Auth Resolution (Week 2)
7. R730 CSDR282: Resolve auth + update
8. R730 1JF7Q22: Resolve auth + update

### Phase 5: Cluster-Wide (Week 3)
9. All servers: NIC firmware updates
10. All servers: RAID controller updates
11. All servers: System CPLD (if available)

---

## Firmware Verification Commands

After downloading, verify firmware integrity:

```bash
# Check file size matches Dell documentation
ls -lh /home/daryl/cluster-bootstrap/firmware/downloads/

# Extract Dell .exe to get firmware binary
7z x iDRAC-with-Lifecycle-Controller_Firmware_GFXKP_WN64_2.83.83.83_A00.EXE

# Or use binwalk if 7z fails
binwalk -e iDRAC-with-Lifecycle-Controller_Firmware_GFXKP_WN64_2.83.83.83_A00.EXE

# Verify extracted firmware
file payload.bin  # Should show "data" or firmware signature
```

---

## Dell Firmware Portal Notes

### Authentication
Dell no longer allows anonymous firmware downloads. You must:
1. Create free Dell account
2. Register service tags to account
3. Download from authenticated session

### Alternative: FTP Mirror (If Available)
Dell maintains FTP mirror for some firmware:
```
ftp://ftp.dell.com/
```
Navigate to: `/published/<model>/firmware/`

### RACADM Alternative
If manual download fails, use RACADM from another server:
```bash
racadm -r 192.168.1.10 -u root -p calvin update -f <firmware_url>
```

---

**Status**: ⏳ AWAITING MANUAL DOWNLOAD
**Files Required**: 6+ firmware packages
**Estimated Download Size**: ~1.2 GB total
**Ready for Phase 3**: After downloads complete + auth resolution
