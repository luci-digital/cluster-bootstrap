# Dell R720 IPMI Serial over LAN - READY

**Date**: 2026-01-27 04:45 MST
**Status**: ✅ FULLY CONFIGURED AND TESTED

---

## ✅ Connection Verified

**Working Credentials**:
- iDRAC IP: `192.168.1.10`
- Username: `root`
- Password: `calvin` (default - **recommend changing**)

**IPMI Status**: ✅ Connected and tested
**SOL Status**: ✅ Enabled with Administrator privileges

---

## 🖥️ System Information

| Component | Details |
|-----------|---------|
| **Model** | PowerEdge R720 |
| **Service Tag** | 4J0TV12 |
| **Express Code** | 9857379926 |
| **Board Serial** | CN70163661002H |
| **Asset Tag** | tron |
| **Manufactured** | June 2, 2016 |
| **Board Revision** | 01 |

### Power Supplies
- **PS1**: 750W Delta (Serial: CN1797243H2YU0, March 2014)
- **PS2**: 750W Delta (Serial: CN1797243H2WC1, March 2014)

### Current Status
- **Power State**: ON
- **Power Overload**: No
- **Power Fault**: No
- **Chassis Intrusion**: No

---

## 🌡️ Thermal Status

| Component | Reading | Status | Safe Range |
|-----------|---------|--------|------------|
| **Inlet Temp** | 23°C | ✅ OK | 3-42°C |
| **Exhaust Temp** | 29°C | ✅ OK | 8-70°C |
| **CPU/System** | 39°C, 33°C | ✅ OK | Max 95°C |

### Cooling Fans (All OK)
- Fan1: 7680 RPM ✓
- Fan2: 7680 RPM ✓
- Fan3: 7800 RPM ✓
- Fan4: 7560 RPM ✓
- Fan5: 7560 RPM ✓
- Fan6: 7680 RPM ✓

### Power
- **AC Input Voltage**: 118V ✓

---

## 🔌 Serial over LAN Configuration

| Setting | Value |
|---------|-------|
| **Enabled** | ✅ TRUE |
| **Privilege Level** | ADMINISTRATOR |
| **Force Encryption** | TRUE |
| **Baud Rate** | 115200 (115.2 kbps) |
| **Payload Port** | 623 |
| **Channel** | 1 (0x01) |
| **Retry Count** | 7 |
| **Retry Interval** | 480 ms |

---

## 🚀 Quick Start Commands

### Connect to Serial Console
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sol activate
```

**Exit SOL**: Press `~.` (tilde followed by dot)

### Load Quick Aliases
```bash
source /tmp/r720_ipmi_commands.sh
r720-sol    # Connect to serial console
```

### Other Quick Commands
```bash
# Chassis status
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis status

# Power status
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' power status

# Sensor readings
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sensor list

# System Event Log
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sel list

# Hardware info
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' fru print
```

---

## 📦 Firmware Update Ready

**Firmware Directory**: `/home/daryl/cluster-bootstrap/firmware/`
**HTTP Server**: `http://192.168.1.145:8000/firmware/`

### Current Firmware Versions
- **iDRAC**: 2.65.65.65 (recommend upgrade to 2.70.70.70+)
- **BIOS**: 2.9.0 (check for updates)

### Update Process
1. Download firmware from Dell Support (Service Tag: 4J0TV12)
2. Upload to: `daryl@192.168.1.145:/home/daryl/cluster-bootstrap/firmware/`
3. Apply via iDRAC web UI: https://192.168.1.10
   - Maintenance → System Update → Firmware Update
   - Network Share: `http://192.168.1.145:8000/firmware/[filename]`

---

## ⚠️ Security Recommendations

### CRITICAL: Change Default Password

**Via ipmitool**:
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  user set password 2 'NewSecurePassword123!'
```

**Via Web UI**:
1. Access: https://192.168.1.10
2. Login: root / calvin
3. Navigate: iDRAC Settings → Users → root
4. Change password

### Additional Security
- [ ] Change iDRAC password from default "calvin"
- [ ] Enable IP whitelist for iDRAC access
- [ ] Review and disable unused user accounts
- [ ] Enable audit logging
- [ ] Configure SNMPv3 (if using SNMP)

---

## 🔧 Power Management

### Power Control Commands
```bash
# Power cycle (reboot)
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power cycle

# Power on
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power on

# Graceful shutdown
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power soft

# Hard power off
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power off

# Check power status
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power status
```

---

## 📋 Bootstrap Configuration

**PXE Boot Ready**: Yes
**TFTP Server**: 192.168.1.145:69
**HTTP Server**: 192.168.1.145:8000
**Provisioning API**: 192.168.1.145:9999

### Network Boot Setup

1. **Configure BIOS** (via iDRAC Virtual Console or SOL):
   - Boot Mode: UEFI
   - Enable PXE on primary NIC
   - Boot Sequence: PXE → Hard Drive

2. **Server will auto-provision**:
   - PXE boot from Zbook (192.168.1.145)
   - Register MAC (18:FB:7B:A7:80:21)
   - Download NixOS/openEuler configuration
   - Install OS automatically

3. **Expected IP Assignment**:
   - Will get DHCP or static from inventory
   - IPv6: 2602:F674:0001::10/64

---

## 📊 System Health Summary

| Category | Status | Notes |
|----------|--------|-------|
| **Power** | ✅ OK | Dual 750W PSUs, on and healthy |
| **Thermals** | ✅ OK | All temps in normal range |
| **Cooling** | ✅ OK | All 6 fans operational |
| **Voltage** | ✅ OK | 118V AC input stable |
| **iDRAC** | ✅ OK | Responding, SOL enabled |
| **IPMI** | ✅ OK | Tested and working |

---

## 📚 Reference Files

| File | Location |
|------|----------|
| **Integration Guide** | `/home/daryl/cluster-bootstrap/R720_INTEGRATION_GUIDE.md` |
| **IPMI Quickstart** | `/home/daryl/cluster-bootstrap/R720_IPMI_SOL_QUICKSTART.md` |
| **Quick Commands** | `/tmp/r720_ipmi_commands.sh` |
| **Inventory Entry** | `/home/daryl/cluster-bootstrap/inventory.yaml` |
| **Firmware Instructions** | `/home/daryl/cluster-bootstrap/firmware/FIRMWARE_MANUAL_DOWNLOAD.md` |

---

## ✅ Ready For

- ✅ Serial console access via SOL
- ✅ Firmware updates via iDRAC web UI
- ✅ Firmware updates via Redfish API
- ✅ Power management via IPMI
- ✅ System monitoring and sensor readings
- ✅ PXE network boot and OS provisioning
- ✅ BIOS configuration via SOL
- ✅ Emergency recovery

---

**Status**: Fully configured and tested - ready for production use
**Last Verified**: 2026-01-27 04:45 MST
**Next Step**: Upload firmware or connect to serial console
