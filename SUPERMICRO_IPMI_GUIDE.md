# Supermicro IPMI/BMC Quick Guide

**Found**: 2 Supermicro servers in your network configuration

---

## 🖥️ Your Supermicro Servers

| Server | IP | MAC Address | Hostname |
|--------|-----|-------------|----------|
| **Supermicro GPU #1** | 192.168.1.200 | 0c:c4:7a:a8:72:14 | supermicro-gpu |
| **Supermicro GPU #2** | 192.168.1.201 | 0c:c4:7a:a8:72:15 | supermicro-gpu-lan2 |

---

## 🔌 Connect to Supermicro IPMI

### Test Connection
```bash
# Ping IPMI interface
ping 192.168.1.200
ping 192.168.1.201

# Test IPMI access (try default credentials)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power status
```

### Default Supermicro Credentials
| Username | Password | Notes |
|----------|----------|-------|
| ADMIN | ADMIN | Most common default |
| admin | admin | Lowercase variant |
| root | superuser | Alternative |

---

## 🎮 Supermicro IPMI Commands

### Power Control
```bash
# Power status
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power status

# Power on
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power on

# Power off (graceful)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power soft

# Power off (hard)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power off

# Power cycle
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power cycle

# Reset
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power reset
```

### Boot Device Selection
```bash
# Boot from PXE (network)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev pxe

# Boot from disk
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev disk

# Boot from CDROM (virtual media)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev cdrom

# Boot from BIOS
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev bios
```

### Serial Over LAN (SOL)
```bash
# Activate serial console
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol activate

# Deactivate (Ctrl-] or Ctrl-\ to exit)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol deactivate

# Enable SOL first (if not working)
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol set enabled true 1
```

### System Information
```bash
# Get BMC info
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN bmc info

# Get FRU (Field Replaceable Unit) info
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN fru

# Sensor readings
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sdr list

# Fan speeds
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sensor get "FAN1"

# Temperatures
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sensor get "CPU Temp"
```

---

## 🌐 Supermicro Web Interface (IPMI over HTTP)

**Access IPMI Web Interface**:
```
https://192.168.1.200
https://192.168.1.201

Login: ADMIN / ADMIN (or admin/admin)
```

**Features**:
- Remote Console (Java/HTML5)
- Virtual Media (mount ISOs remotely)
- Power control
- Sensor monitoring
- BIOS configuration

---

## 💿 Virtual Media on Supermicro

Supermicro virtual media works via:

### Option 1: Web Interface (Easiest)
1. Open https://192.168.1.200
2. Login: ADMIN/ADMIN
3. Go to **Remote Control** → **iKVM/HTML5**
4. Click **Virtual Media** button
5. Select **CD-ROM Image**
6. Enter URL: `http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso`
7. Click **Mount**
8. Boot from virtual CD

### Option 2: PXE Boot (Pure IPMI - RECOMMENDED)
```bash
# Set boot to PXE
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev pxe

# Power cycle
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power cycle

# Watch via serial console
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol activate
```

### Option 3: IPMIView (Java Tool)
Supermicro provides IPMIView for virtual media:
```bash
# Download from Supermicro
wget https://www.supermicro.com/wdl/utility/IPMIView/Linux/IPMIView20.jar

# Run
java -jar IPMIView20.jar
```

---

## 🚀 Quick Deploy Script for Supermicro

```bash
#!/bin/bash
# deploy-supermicro.sh

IPMI_HOST="${1:-192.168.1.200}"
IPMI_USER="ADMIN"
IPMI_PASS="ADMIN"

echo "Deploying to Supermicro at $IPMI_HOST..."

# Function to run IPMI commands
ipmi() {
  ipmitool -I lanplus -H "$IPMI_HOST" -U "$IPMI_USER" -P "$IPMI_PASS" "$@"
}

# Check connectivity
echo "Testing IPMI connectivity..."
ipmi chassis power status || {
  echo "Failed to connect. Check IP/credentials."
  exit 1
}

# Set boot to PXE
echo "Setting boot device to PXE..."
ipmi chassis bootdev pxe

# Power cycle
echo "Power cycling server..."
ipmi chassis power cycle

# Wait for boot
sleep 5

# Connect to console
echo "Connecting to serial console (Ctrl-] to exit)..."
ipmi sol activate
```

**Usage**:
```bash
chmod +x deploy-supermicro.sh
./deploy-supermicro.sh 192.168.1.200  # GPU server 1
./deploy-supermicro.sh 192.168.1.201  # GPU server 2
```

---

## 🔧 Add Supermicro DNS Entries

```bash
# Add to /etc/hosts
echo "
# Supermicro IPMI
192.168.1.200   supermicro-gpu supermicro1.local
192.168.1.201   supermicro-gpu-lan2 supermicro2.local
" | sudo tee -a /etc/hosts

# Test
ping supermicro1.local
```

---

## 📊 Supermicro vs Dell Comparison

| Feature | Supermicro IPMI | Dell iDRAC |
|---------|-----------------|------------|
| **Default User** | ADMIN | root |
| **Default Pass** | ADMIN | calvin |
| **Web Port** | 443 (HTTPS) | 443 (HTTPS) |
| **IPMI Commands** | ✅ Same (ipmitool) | ✅ Same (ipmitool) |
| **Virtual Media** | Web UI or IPMIView | Web UI or RACADM |
| **CLI Tool** | IPMIView (Java) | RACADM |
| **Remote Console** | iKVM/HTML5 | Virtual Console |

---

## 🎯 Recommended Workflow

**For GPU Supermicro servers**:

1. **Test IPMI access**:
```bash
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power status
```

2. **Boot via PXE** (pure IPMI):
```bash
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev pxe
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power cycle
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol activate
```

3. **Select from PXE menu**:
   - openEuler 25.09
   - Bootimus FreeBSD
   - netboot.xyz

---

## 🚨 Troubleshooting

### Can't Connect to IPMI
```bash
# Check if IP is reachable
ping 192.168.1.200

# Try different credentials
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power status
ipmitool -I lanplus -H 192.168.1.200 -U admin -P admin chassis power status
ipmitool -I lanplus -H 192.168.1.200 -U root -P superuser chassis power status
```

### SOL Not Working
```bash
# Enable SOL
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol set enabled true 1
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol set privilege-level admin 1

# Try again
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol activate
```

### Web Interface Not Loading
- Try HTTP: http://192.168.1.200 (may redirect to HTTPS)
- Accept self-signed certificate
- Try different browser (Chrome, Firefox)
- Check firewall: `sudo firewall-cmd --list-all`

---

## 📋 Summary

**Your Supermicro Servers**:
- **192.168.1.200** (supermicro-gpu)
- **192.168.1.201** (supermicro-gpu-lan2)

**Quick Commands**:
```bash
# Power status
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power status

# PXE boot
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis bootdev pxe
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN chassis power cycle

# Serial console
ipmitool -I lanplus -H 192.168.1.200 -U ADMIN -P ADMIN sol activate
```

**Web UI**: https://192.168.1.200 (ADMIN/ADMIN)

🚀 **Ready to deploy to Supermicro!**
