# Phase 2: Manual Firmware Download Required

**Status**: Dell blocks automated downloads - manual intervention needed
**Date**: 2026-01-27
**Priority**: R720 iDRAC update is CRITICAL

---

## Critical Finding: R720 iDRAC 2.65.65.65 is Outdated

Your R720 "tron" (192.168.1.10) is running **iDRAC7 version 2.65.65.65**, which is several versions behind.

### What You Need to Download

| Server | Component | Current | Target | Priority |
|--------|-----------|---------|--------|----------|
| **R720 tron** | iDRAC7 | 2.65.65.65 | Latest (2.70+) | 🔴 CRITICAL |
| **R720 tron** | BIOS | 2.9.0 | Latest | Medium |
| R730 ORION | BIOS | 2.19.0 | Latest | Low (verify if already latest) |
| R730 ESXi5 | BIOS | ? | Latest | Low |

---

## Step-by-Step Download Instructions

### 1. R720 iDRAC7 Firmware (HIGHEST PRIORITY)

**Visit**: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers

**Steps**:
1. Click "View all drivers" or filter by:
   - Category: **"Systems Management"** or **"iDRAC with Lifecycle Controller"**
   - Operating System: **"Independent"** or **"BIOS"**

2. Look for file named:
   - `iDRAC-with-Lifecycle-Controller_Firmware_*.BIN` (Linux/Redfish)
   - OR `iDRAC-with-Lifecycle-Controller_Firmware_*.EXE` (Windows)
   - **Prefer .BIN format** for Redfish HTTP push

3. Download the **latest version available** (target 2.70.70.70 or higher)

4. Save as: `/home/daryl/cluster-bootstrap/firmware/r720-idrac-{version}.BIN`

**Known Versions** (from community):
- 2.70.70.70 (target)
- 2.65.65.65 (your current - OUTDATED)
- 2.63.60.61
- 2.60.60.60

**Why This is Critical**: Old iDRAC versions have:
- Security vulnerabilities
- Limited Redfish API features
- Potential stability issues
- Missing compatibility with newer tools

---

### 2. R720 BIOS (Secondary Priority)

**Same page**: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers

**Steps**:
1. Filter by Category: **"BIOS"**

2. Look for:
   - File: `BIOS_*.BIN` or `BIOS_*.EXE`
   - Current: 2.9.0
   - Check if newer version exists

3. Known link (verify version): https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=nppky

4. Save as: `/home/daryl/cluster-bootstrap/firmware/r720-bios-{version}.BIN`

---

### 3. R730 BIOS (Low Priority - May Already Be Latest)

**Visit**: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r730/drivers

**Steps**:
1. Filter by Category: **"BIOS"**

2. **Important**: Your R730 ORION is already at **2.19.0**
   - Community reports show 2.16.0, 2.15.0 as available
   - **You may already be on the latest version!**
   - Check the site to confirm 2.19.0 is current

3. If newer version exists, download:
   - File: `BIOS_*.BIN` for R630/R730/R730XD
   - Save as: `/home/daryl/cluster-bootstrap/firmware/r730-bios-{version}.BIN`

4. Known link (2.16.0): https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7557v

---

## Alternative: Dell Server Update Utility (SUU)

If individual downloads are difficult, download the Dell SUU ISO:

**Link**: https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=111d5

**Benefits**:
- Contains ALL latest firmware for your servers
- Bootable ISO with automated update
- Can extract individual .BIN files from ISO

**How to Extract**:
```bash
# Mount ISO
sudo mount -o loop Dell-SUU-*.iso /mnt

# Copy firmware files
cp /mnt/repository/iDRAC-* /home/daryl/cluster-bootstrap/firmware/
cp /mnt/repository/BIOS_* /home/daryl/cluster-bootstrap/firmware/

# Unmount
sudo umount /mnt
```

---

## After Download

1. **Verify files are in place**:
   ```bash
   ls -lh /home/daryl/cluster-bootstrap/firmware/*.BIN
   ```

2. **Test HTTP accessibility** (HTTP server should be running):
   ```bash
   curl -I http://192.168.1.145:8000/r720-idrac-*.BIN
   ```

3. **Proceed to Phase 3**: Run the Redfish update script

---

## File Naming Convention

Please rename downloaded files for clarity:

| Original | Rename To |
|----------|-----------|
| `iDRAC-with-Lifecycle-Controller_Firmware_XXXXX_WN64_2.70.70.70_A00.BIN` | `r720-idrac-2.70.70.70.BIN` |
| `BIOS_XXXXX_WN64_2.9.0_A00.BIN` | `r720-bios-2.9.0.BIN` |
| `BIOS_XXXXX_WN64_2.19.0_A00.BIN` | `r730-bios-2.19.0.BIN` |

---

## Verification Commands

After placing files:

```bash
# List downloaded firmware
ls -lh /home/daryl/cluster-bootstrap/firmware/*.BIN

# Calculate SHA256 checksums (compare with Dell site)
sha256sum /home/daryl/cluster-bootstrap/firmware/*.BIN

# Test HTTP server
curl -I http://192.168.1.145:8000/r720-idrac-2.70.70.70.BIN
```

---

## Important Notes

1. **Dell Account**: Some downloads may require Dell account login
2. **Service Tag**: You can enter service tag (4J0TV12 for R720) for customized downloads
3. **File Format**:
   - **Prefer .BIN** for Linux/Redfish updates
   - .EXE files work but require Windows or extraction
4. **iDRAC7 vs iDRAC8**: R720 uses iDRAC7, R730 uses iDRAC8 (different firmware)
5. **Current Status**:
   - R730s have current iDRAC (2.86.86.86) ✅
   - Only R720 iDRAC needs update 🔴

---

## Sources & References

- [PowerEdge R720 Support](https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers)
- [PowerEdge R730 Support](https://www.dell.com/support/home/en-us/product-support/product/poweredge-r730/drivers)
- [Dell Firmware Update Methods](https://www.dell.com/support/kbdoc/en-us/000128194/updating-firmware-and-drivers-on-dell-emc-poweredge-servers)
- [R720 BIOS Details](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=nppky)
- [R730 BIOS 2.16.0 Details](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7557v)
- [Dell Server Update Utility](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=111d5)

---

## Next Steps

Once you've downloaded the firmware files:

1. Place them in `/home/daryl/cluster-bootstrap/firmware/`
2. Verify HTTP server is running (port 8000)
3. Run Phase 3 update script (will be provided)

**Priority Order**:
1. R720 iDRAC update (CRITICAL) 🔴
2. R720 BIOS update
3. R730 BIOS updates (if newer versions exist)

---

**Status**: ⏸️ PAUSED - Awaiting manual firmware download
