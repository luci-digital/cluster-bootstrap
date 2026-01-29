# Dell R720 Integration Guide - LuciVerse Bootstrap

**Server**: PowerEdge R720 (Service Tag: 4J0TV12)
**iDRAC IP**: 192.168.1.10
**Discovered**: 2026-01-27
**Status**: Ready for firmware & bootstrap

---

## Server Specifications

| Component | Details |
|-----------|---------|
| **Model** | PowerEdge R720 |
| **Service Tag** | 4J0TV12 |
| **Express Code** | 9857379926 |
| **Hostname** | WIN-RDH12P80O7P |
| **Current OS** | Windows Server |
| **Power State** | ON |

### iDRAC Configuration

| Setting | Value |
|---------|-------|
| **IP Address** | 192.168.1.10 |
| **MAC Address** | 18:FB:7B:A7:80:21 |
| **IPv6** | fd17:ff75:93f0:46b7:1afb:7bff:fea7:8021 |
| **Firmware** | 2.65.65.65 |
| **BIOS** | 2.9.0 |
| **Lifecycle** | 2.65.65.65 |
| **License** | Enterprise ✓ |
| **Web UI** | https://192.168.1.10 |

---

## Zbook Provisioning Server

**Target**: 192.168.1.145 (zbook.lucidigital.net)

### Active Services

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| HTTP Config Server | 8000 | ✅ Running | Firmware & bootstrap files |
| Provisioning API | 9999 | ✅ Running | MAC registration & config |
| TFTP Server | 69 | ✅ Running | PXE boot files |

### Directory Structure

```
/home/daryl/cluster-bootstrap/
├── firmware/                    # Firmware files (HTTP accessible)
├── nixos/                       # NixOS configurations
├── inventory.yaml               # Server inventory
├── provision-listener.py        # Provisioning service
└── setup-netboot.sh            # PXE setup script
```

---

## Firmware Update Process

### Step 1: Upload Firmware to Zbook

**Method A: SCP Upload**
```bash
scp iDRAC-firmware.bin daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/
```

**Method B: From Zbook Terminal**
```bash
cd /home/daryl/cluster-bootstrap/firmware/
wget https://dl.dell.com/FOLDER/FILE/iDRAC-firmware.bin
```

### Step 2: Apply Firmware via iDRAC

**Web UI Method** (Recommended):

1. **Access iDRAC**
   - URL: https://192.168.1.10
   - Login with your credentials

2. **Navigate to Update**
   - Go to: **Maintenance** → **System Update**
   - Click: **Firmware Update**

3. **Configure Network Source**
   - Method: **Network Share** or **HTTP**
   - Server: `192.168.1.145`
   - Share Type: `HTTP`
   - Share Name: `firmware`
   - File Name: `[your-firmware-file]`
   - Full URL: `http://192.168.1.145:8000/firmware/[filename]`

4. **Apply Update**
   - Click **Check for Updates**
   - Select firmware package
   - Click **Install and Reboot** or **Install Now**

**Redfish API Method**:
```bash
curl -k -u root:YOUR_PASSWORD -X POST \
  https://192.168.1.10/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate \
  -H "Content-Type: application/json" \
  -d '{
    "ImageURI": "http://192.168.1.145:8000/firmware/iDRAC-firmware.bin",
    "TransferProtocol": "HTTP"
  }'
```

### Step 3: Verify Update

```bash
# Check iDRAC version after reboot
curl -k -s -u root:PASSWORD \
  https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1 \
  | jq '.FirmwareVersion'
```

---

## OS Bootstrap Process (Optional)

After firmware updates, you can bootstrap the server to NixOS or openEuler.

### Prerequisites

1. **Backup Windows Data** (if needed)
2. **Clear RAID Configuration** (or configure as desired)
3. **Configure BIOS for PXE Boot**

### BIOS Configuration

**Access BIOS** (via iDRAC Virtual Console or F2 during boot):

1. **Boot Mode**
   - System Setup → Boot Settings
   - Boot Mode: **UEFI** (recommended)
   - Alternative: **BIOS** (legacy)

2. **Network Boot**
   - Integrated Devices → Network Settings
   - Enable: **PXE Device 1** (primary NIC)
   - Enable: **PXE Device 2** (if using bonding)

3. **Boot Sequence**
   - Boot Settings → Boot Sequence
   - 1st: **PXE Device 1**
   - 2nd: **Hard Drive C:**
   - Save and Exit

### PXE Boot Flow

```
R720 Power On
    ↓
UEFI/BIOS checks boot order
    ↓
PXE request to network (MAC: 18:FB:7B:A7:80:21)
    ↓
Zbook TFTP responds (192.168.1.145:69)
    ↓
Download PXE boot files
    ↓
Execute bootstrap script (HTTP from :8000)
    ↓
Register MAC with provisioning service (:9999)
    ↓
Get server-specific NixOS/openEuler config
    ↓
Download & install OS
    ↓
Reboot into new OS
```

### Provisioning Listener

The provisioning service at port 9999 will:
- Detect MAC address: `18:FB:7B:A7:80:21`
- Look up in `inventory.yaml`
- Generate server-specific config
- Assign IPv4: (DHCP or static from inventory)
- Assign IPv6: `2602:F674:0001::10/64`
- Provide NixOS configuration

### Manual Bootstrap Trigger

```bash
# From Zbook, trigger bootstrap for R720
curl -X POST http://localhost:9999/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "mac": "18:FB:7B:A7:80:21",
    "service_tag": "4J0TV12",
    "os": "nixos"
  }'
```

---

## Recommended Firmware Updates

### Current Versions
- iDRAC: **2.65.65.65** → Target: **2.70.70.70+**
- BIOS: **2.9.0** → Target: **2.9.0+** (check latest)
- Lifecycle Controller: **2.65.65.65** → Updates with iDRAC

### Update Priority

1. **iDRAC Firmware** (High Priority)
   - Security patches
   - Redfish API improvements
   - Better remote management
   - Download: Dell Support site for 4J0TV12

2. **BIOS Update** (Medium Priority)
   - CPU microcode updates
   - Memory compatibility
   - Stability improvements

3. **Network Adapters** (Medium Priority)
   - If using 10GbE cards
   - Broadcom or Intel NIC firmware

4. **PERC RAID Controller** (Medium Priority)
   - If using hardware RAID
   - Check current PERC model first

5. **Lifecycle Controller** (Low Priority)
   - Usually updates with iDRAC
   - Check if separate update available

### Download Links

**Dell Support Portal**:
- Direct: https://www.dell.com/support/home/product-support/servicetag/4J0TV12
- Search: "PowerEdge R720 firmware"
- Filter: iDRAC, BIOS, PERC, Network

**Repository Server** (if configured):
- FTP: ftp.dell.com
- HTTP: downloads.dell.com

---

## Network Configuration

### Current Network

| Interface | Type | IP | MAC |
|-----------|------|-----|-----|
| iDRAC | Management | 192.168.1.10 | 18:FB:7B:A7:80:21 |
| Eth0 | Primary NIC | (DHCP from Windows) | (Check in OS) |
| Eth1 | Secondary NIC | (Check config) | (Check in OS) |

### Post-Bootstrap Network

After NixOS/openEuler installation:
- Host IP: Will be assigned by inventory config
- IPv6: 2602:F674:0001::10/64
- iDRAC IP: 192.168.1.10 (unchanged)

---

## Troubleshooting

### Firmware Update Issues

**Problem**: iDRAC can't reach HTTP server
```bash
# Verify Zbook HTTP service
systemctl status luciverse-http

# Test from R720 iDRAC
# In iDRAC web UI: Diagnostics → Network → Ping
# Target: 192.168.1.145
```

**Problem**: Update fails with "Invalid file"
- Ensure firmware file is correct for R720
- Check file integrity (MD5/SHA checksums)
- Try different firmware version

**Problem**: iDRAC unresponsive after update
- Wait 5-10 minutes (iDRAC may reboot multiple times)
- Power cycle server if needed
- Use iDRAC reset button (physical access required)

### PXE Boot Issues

**Problem**: Server doesn't PXE boot
```bash
# Verify TFTP service on Zbook
sudo systemctl status dnsmasq
sudo ss -tulnp | grep :69

# Check PXE files exist
ls -la /srv/tftp/
```

**Problem**: MAC not registered
```bash
# Check provisioning listener logs
journalctl -u luciverse-provision -f

# Manually register MAC
curl -X POST http://localhost:9999/register \
  -d '{"mac": "18:FB:7B:A7:80:21"}'
```

**Problem**: Gets IP but can't download bootstrap
```bash
# Verify HTTP service
curl http://192.168.1.145:8000/

# Check bootstrap script exists
ls -la /home/daryl/cluster-bootstrap/bootstrap.sh
```

---

## Next Steps

### Immediate (Firmware Update)
1. ✅ Server identified and added to inventory
2. ✅ Zbook provisioning services verified
3. ✅ Firmware directory created
4. ⏳ Upload firmware files to Zbook
5. ⏳ Apply firmware via iDRAC web UI
6. ⏳ Verify updates successful

### Optional (OS Bootstrap)
7. ⏳ Backup Windows data (if needed)
8. ⏳ Configure BIOS for PXE boot
9. ⏳ Test PXE boot to Zbook
10. ⏳ Install NixOS/openEuler
11. ⏳ Verify OS installation
12. ⏳ Join to LuciVerse cluster

---

## Reference Commands

```bash
# Check Zbook services status
systemctl status luciverse-http luciverse-provision

# View provisioning logs
journalctl -u luciverse-provision -f

# Test HTTP server
curl http://192.168.1.145:8000/

# List firmware files
ls -lah /home/daryl/cluster-bootstrap/firmware/

# Ping R720 iDRAC
ping 192.168.1.10

# Access iDRAC Redfish API
curl -k -s -u root:PASSWORD \
  https://192.168.1.10/redfish/v1/ | jq

# View R720 inventory entry
cat /home/daryl/cluster-bootstrap/inventory.yaml | grep -A 30 "r720_win"
```

---

**Status**: ✅ Ready for firmware upload and update
**Last Updated**: 2026-01-27 04:12 MST
**Contact**: daryl@lucidigital.net
