# Dell Cluster Firmware Download Guide

**Generated**: 2026-01-27
**Status**: Manual download required (Dell blocks automated downloads)

## Priority 1: R720 iDRAC Update (2.65.65.65 → Latest)

### Download Instructions

1. **Visit Dell Support for R720**:
   - URL: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers
   - Service Tag: 4J0TV12

2. **Filter for iDRAC Firmware**:
   - Category: "Systems Management" or "iDRAC with Lifecycle Controller"
   - Operating System: "Independent"
   - Look for: "iDRAC7 Enterprise" or "Integrated Dell Remote Access Controller"

3. **Expected File**:
   - Name: Something like `iDRAC-with-Lifecycle-Controller_Firmware_*.BIN` or `iDRAC-with-Lifecycle-Controller_Firmware_*.EXE`
   - Target Version: 2.70.70.70 or latest available for R720
   - **Note**: Based on search results, 2.70 may not exist for R720 (uses iDRAC7)
   - Latest known versions: 2.65.65.65, 2.63.60.61, 2.60.60.60
   - **Action**: Download the absolute latest available version

4. **Download Location**:
   - Save to: `/home/daryl/cluster-bootstrap/firmware/`
   - Filename format: `r720-idrac-{version}.bin` (rename for clarity)

## Priority 2: R720 BIOS Update (2.9.0 → Latest)

### Download Instructions

1. **Visit same R720 support page**:
   - Filter for: "BIOS"
   - Category: "BIOS"

2. **Expected File**:
   - Current: BIOS 2.9.0
   - Latest available: Check Dell site (search found 2.9.0 as recent)
   - Direct link: https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=nppky

3. **Download**:
   - File format: `.EXE` (Windows) or `.BIN` (Linux/bootable)
   - Prefer `.BIN` format for Redfish HTTP push
   - Save to: `/home/daryl/cluster-bootstrap/firmware/r720-bios-{version}.bin`

## Priority 3: R730 BIOS Update (2.19.0 → Latest)

### Download Instructions

1. **Visit Dell Support for R730**:
   - URL: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r730/drivers
   - Service Tag: CQ5QBM2

2. **Filter for BIOS**:
   - Category: "BIOS"
   - Known versions: 2.16.0, 2.15.0 documented
   - Current: 2.19.0 (already newer than documented versions!)
   - **Check if 2.19.0 is actually the latest**

3. **Download** (if newer version exists):
   - Direct link reference: https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7557v (version 2.16.0)
   - Save to: `/home/daryl/cluster-bootstrap/firmware/r730-bios-{version}.bin`

## Dell Server Update Utility (Alternative Method)

If individual downloads are difficult, consider Dell SUU (Server Update Utility):
- Download: https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=111d5
- Creates bootable ISO with all latest firmware
- Can extract individual firmware files from ISO

## After Download

1. **Place files in**: `/home/daryl/cluster-bootstrap/firmware/`

2. **Verify HTTP accessibility**:
   ```bash
   # Start HTTP server if not running
   cd /home/daryl/cluster-bootstrap/firmware
   python3 -m http.server 8000 &

   # Test access
   curl -I http://192.168.1.145:8000/firmware/r720-idrac-*.bin
   ```

3. **Proceed to Phase 3**: Redfish firmware update

## Important Notes

- **iDRAC7 Version Clarification**: R720 uses iDRAC7, max version may be 2.65.65.65 or 2.70.70.70
- **BIOS 2.9.0**: Already latest for R720 (verify on Dell site)
- **BIOS 2.19.0**: R730 already on newer version than documented (2.16.0)
- **File Format**: Prefer `.BIN` files for Redfish SimpleUpdate
- **Authentication**: Dell site requires login for some downloads

## Sources

- [PowerEdge R720 BIOS Details](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=nppky)
- [R720 Support Page](https://www.dell.com/support/product-details/en-us/product/poweredge-r720/drivers)
- [R730 BIOS 2.16.0 Details](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7557v)
- [R730 Support Page](https://www.dell.com/support/product-details/en-us/product/poweredge-r730/drivers)
- [Dell Firmware Update Methods](https://www.dell.com/support/kbdoc/en-us/000128194/updating-firmware-and-drivers-on-dell-emc-poweredge-servers)
