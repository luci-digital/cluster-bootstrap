# Dell R720 Firmware - Manual Download Required

Dell's direct download links require authentication. Please download firmware manually:

## Download from Dell Support

**Direct Support Page**:
https://www.dell.com/support/home/product-support/servicetag/4J0TV12/drivers

### Required Firmware (Priority Order)

1. **iDRAC with Lifecycle Controller** (CRITICAL)
   - Current: 2.65.65.65
   - Target: 2.70.70.70 or later
   - Search: "iDRAC" or "Integrated Dell Remote Access Controller"
   - File: iDRAC-with-Lifecycle-Controller_Firmware_*.BIN
   - Size: ~40-50MB

2. **BIOS** (HIGH)
   - Current: 2.9.0
   - Target: 2.9.0 (current is latest) or check for updates
   - Search: "BIOS"
   - File: BIOS_*_LN_*.BIN
   - Size: ~10-15MB

3. **Network Adapter - Broadcom 5720** (MEDIUM)
   - Search: "Broadcom" or "Network Firmware"
   - File: Network_Firmware_*.BIN
   - Size: ~5-10MB

### Alternative: Dell Repository Manager

If you have Dell Repository Manager installed:
- Connect to: ftp.dell.com
- Navigate to: /catalog
- Filter by: PowerEdge R720, Service Tag 4J0TV12

### After Download

Upload to Zbook:
```bash
scp iDRAC-firmware.BIN daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/
```

Or place files in: `/home/daryl/cluster-bootstrap/firmware/`
