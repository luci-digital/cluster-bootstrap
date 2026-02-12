# Dell R720 Firmware Download Guide

**Server**: PowerEdge R720
**Service Tag**: 4J0TV12
**Express Code**: 9857379926

## Current Firmware Versions

| Component | Current Version | Target Version |
|-----------|----------------|----------------|
| iDRAC | 2.65.65.65 | 2.70.70.70+ |
| BIOS | 2.9.0 | 2.9.0 (latest) |
| Broadcom 5720 NIC | Unknown | 20.6.101+ |

## Automated Download Failed

Dell's download servers require authentication and block automated tools. Please download manually.

## Manual Download Instructions

### Step 1: Access Dell Support

Visit: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers

Or search by Service Tag: https://www.dell.com/support/home/product-support/servicetag/4J0TV12/drivers

### Step 2: Download Required Firmware (Priority Order)

#### 1. iDRAC with Lifecycle Controller (CRITICAL - Required for remote management)

**Search for**: "iDRAC" or "Integrated Dell Remote Access Controller"

**File naming pattern**: `iDRAC-with-Lifecycle-Controller_Firmware_*_LN_2.70.70.70_A00.BIN`

**Details**:
- Version: 2.70.70.70 or later
- Size: ~40-50MB
- Category: Systems Management
- Type: Firmware

**Why critical**: Current version 2.65.65.65 may have security vulnerabilities and limited Redfish API support

#### 2. BIOS (HIGH Priority)

**Search for**: "BIOS"

**File naming pattern**: `BIOS_*_LN_2.9.0.BIN`

**Details**:
- Version: 2.9.0 (verify if newer available)
- Size: ~10-15MB
- Category: BIOS

**Why important**: Stability, security patches, CPU microcode updates

#### 3. Broadcom NetXtreme 5720 Network Adapter (MEDIUM Priority)

**Search for**: "Broadcom" or "Network Firmware"

**File naming pattern**: `Network_Firmware_*_LN_*.BIN`

**Details**:
- Version: 20.6.101 or later
- Size: ~5-10MB
- Category: Network

**Why useful**: Network performance and stability improvements

### Step 3: Upload to Firmware Server

After downloading, upload files to Zbook:

```bash
# From your local machine (where files were downloaded)
scp iDRAC-with-Lifecycle-Controller_Firmware_*_LN_*.BIN daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/
scp BIOS_*_LN_*.BIN daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/
scp Network_Firmware_*_LN_*.BIN daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/
```

Or place directly on Zbook at: `/home/daryl/cluster-bootstrap/firmware/`

### Step 4: Verify Files

After upload, verify files are accessible:

```bash
# On Zbook
ls -lh /home/daryl/cluster-bootstrap/firmware/*.BIN

# Test HTTP access
curl -I http://192.168.1.145:8000/firmware/iDRAC*.BIN
```

## Alternative: Dell Repository Manager

If available:
1. Install Dell Repository Manager
2. Connect to Dell's repository
3. Filter by: PowerEdge R720, Service Tag 4J0TV12
4. Download firmware bundles

## Alternative: Dell EMC OpenManage

Use Dell's OpenManage tools:
- OpenManage Server Administrator
- Dell Update Package (DUP) downloads

## After Files Are Downloaded

Once firmware files are uploaded, run:

```bash
cd /home/daryl/cluster-bootstrap/firmware
./apply-firmware-updates.sh
```

This will automatically apply updates via Redfish API.

## Support Resources

- Dell Support: https://www.dell.com/support
- Dell Community Forums: https://www.dell.com/community
- Dell TechDirect (for partners): https://techdirect.dell.com

## Notes

- Downloads require Dell account (free registration)
- Some firmware may be behind support contracts
- Verify checksums if provided by Dell
- Keep firmware files for future use/rollback
