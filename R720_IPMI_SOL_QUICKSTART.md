# Dell R720 IPMI Serial over LAN - Quick Start

**Server**: PowerEdge R720 (4J0TV12)
**iDRAC IP**: 192.168.1.10
**Status**: ✅ IPMI Enabled, Ready for SOL

---

## 🚀 Quick Setup (Automated)

```bash
# Run automated setup (prompts for password)
bash /tmp/ipmi_sol_setup.sh
```

This script will:
- Test IPMI connectivity
- Enable Serial over LAN
- Configure privilege level to Administrator
- Display chassis and power status
- Save credentials to environment file

---

## 🔧 Manual IPMI Commands

Replace `PASSWORD` with your iDRAC root password.

### Test Connection
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' chassis status
```

### Enable SOL
```bash
# Enable Serial over LAN
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  sol set enabled true 1

# Set privilege level
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  sol set privilege-level admin 1

# Verify SOL settings
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  sol info 1
```

### Connect to Serial Console
```bash
# Activate SOL (connect to serial console)
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' sol activate

# To exit: Press ~ then . (tilde-dot)
# Or from another terminal:
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' sol deactivate
```

### Power Management
```bash
# Check power status
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  chassis power status

# Power cycle
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  chassis power cycle

# Power on
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  chassis power on

# Power off (graceful)
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  chassis power soft

# Power off (hard)
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' \
  chassis power off
```

### System Information
```bash
# Get sensor readings
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' sensor list

# Get System Event Log
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' sel list

# Get FRU (Field Replaceable Unit) info
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' fru print

# Get BMC info
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PASSWORD' bmc info
```

---

## 📦 Firmware Update via IPMI

After downloading firmware to `/home/daryl/cluster-bootstrap/firmware/`:

### Option 1: Web UI (Easiest)
1. Access: https://192.168.1.10
2. Go to: Maintenance → System Update → Firmware Update
3. Select: Network Share / HTTP
4. URL: `http://192.168.1.145:8000/firmware/[filename]`
5. Apply update

### Option 2: Redfish API
```bash
# Apply firmware update via Redfish
curl -k -u root:PASSWORD -X POST \
  https://192.168.1.10/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate \
  -H "Content-Type: application/json" \
  -d '{
    "ImageURI": "http://192.168.1.145:8000/firmware/iDRAC-2.70.70.70-R720.BIN",
    "TransferProtocol": "HTTP"
  }'
```

### Option 3: IPMI (Limited)
IPMI can trigger updates but firmware must be downloaded via web UI or Redfish.

---

## 🖥️ Serial Console via SOL

Once SOL is activated, you have full serial console access:

**Use Cases**:
- Watch boot process
- Access BIOS/UEFI setup (press F2)
- Monitor POST errors
- Access OS console (if serial console configured)
- Emergency recovery

**Key Sequences**:
- `~.` - Exit SOL session
- `~~` - Send literal tilde
- `~?` - Help

**Windows Server Access**:
To enable serial console in Windows:
```cmd
bcdedit /ems on
bcdedit /emssettings EMSPORT:2 EMSBAUDRATE:115200
```

**Linux Access**:
Serial console usually works by default. Add to kernel params:
```
console=tty0 console=ttyS1,115200n8
```

---

## 🔐 Security Best Practices

### Change Default Password
```bash
# Via ipmitool
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'OLD_PASSWORD' \
  user set password 2 NEW_PASSWORD

# Via web UI
# Settings → Users → root → Change Password
```

### Limit Access
- Use dedicated management VLAN
- Enable encryption (already configured based on your settings)
- Use strong passwords
- Disable unused user accounts
- Enable audit logging

---

## 📋 Quick Reference

| Task | Command |
|------|---------|
| **Setup SOL** | `bash /tmp/ipmi_sol_setup.sh` |
| **Connect** | `ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PWD' sol activate` |
| **Disconnect** | Press `~.` or run deactivate from another terminal |
| **Power Status** | `ipmitool ... chassis power status` |
| **Power Cycle** | `ipmitool ... chassis power cycle` |
| **Sensors** | `ipmitool ... sensor list` |
| **Event Log** | `ipmitool ... sel list` |

---

## 🆘 Troubleshooting

### Cannot connect to IPMI
```bash
# Test ping
ping 192.168.1.10

# Test IPMI port
nc -zv 192.168.1.10 623

# Check iDRAC settings in web UI
# Settings → Network → IPMI Settings
# Ensure "Enable IPMI Over LAN" is checked
```

### Authentication fails
- Verify username (usually `root`)
- Check password
- Verify privilege level (Administrator required for SOL)
- Check user is not disabled in web UI

### SOL not working
```bash
# Check SOL is enabled
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PWD' sol info 1

# Enable if disabled
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'PWD' sol set enabled true 1
```

### Cannot exit SOL
- Press `~.` (tilde then dot)
- From another terminal: `ipmitool ... sol deactivate`
- Kill terminal session

---

## 📚 Additional Resources

- Dell iDRAC User Guide: https://www.dell.com/support/manuals/poweredge-r720
- IPMI Specification: https://www.intel.com/content/www/us/en/products/docs/servers/ipmi/
- ipmitool Man Page: `man ipmitool`

---

**Status**: ✅ Ready for IPMI SOL connection
**Last Updated**: 2026-01-27 04:40 MST
