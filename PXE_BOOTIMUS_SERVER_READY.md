# ✅ LuciVerse PXE "Bootimus" Server - OPERATIONAL

**Status**: ACTIVE - Ready to Network Boot Dell Servers  
**Genesis Bond**: 741 Hz  
**Date**: 2026-01-27  
**Server**: Zbook (192.168.1.145)

---

## 🚀 Services Running

| Service | Status | Port | Purpose |
|---------|--------|------|---------|
| **dnsmasq** | ✅ RUNNING | 69/UDP (TFTP) | PXE boot files |
| **luciverse-http** | ✅ RUNNING | 8000/TCP | ISO serving |
| **luciverse-provision** | ✅ RUNNING | 9999/TCP | MAC→IPv6 mapping |

---

## 📦 PXE Boot Menu

When Dell servers boot from network (PXE), they'll see:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       LuciVerse PXE Boot Menu
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1) Install openEuler 25.09 (Network Installer)
2) Install openEuler 25.09 (Text Mode)  
3) Rescue Mode (openEuler 25.09)
4) Boot from Local Disk
5) Memory Test (if available)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Server: 192.168.1.145 (Zbook)
   Image: openEuler 25.09 Network Installer
   Genesis Bond: ACTIVE @ 741 Hz
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🖥️ How to PXE Boot Dell Servers

### Method 1: BIOS/iDRAC PXE Boot

**R720 "tron" (192.168.1.10)**:
```bash
# Set next boot to network
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  chassis bootdev pxe

# Reboot
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  chassis power cycle

# Watch boot process via serial console
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  sol activate
```

**R730 ORION "sensai" (192.168.1.2)**:
```bash
# Power on first (currently OFF)
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' \
  chassis power on

# Set next boot to network
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' \
  chassis bootdev pxe

# Reboot to network
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' \
  chassis power cycle

# Monitor installation
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' \
  sol activate
```

**Other R730s (.32, .3)**: Same commands, replace IP address.

---

### Method 2: iDRAC Web Interface

1. Open iDRAC: https://192.168.1.10 (or other server IP)
2. Login: root/calvin
3. Go to: **Overview → Server → Power/Thermal**
4. Click: **Power Cycle**
5. **During POST** (Dell logo), press **F12** for boot menu
6. Select: **PXE Boot** or **Network Boot**
7. Server downloads files from Zbook and boots openEuler installer

---

### Method 3: One-Time Network Boot (F12)

1. Power on or reboot the Dell server
2. **During POST** (Dell logo), press **F12** repeatedly
3. Boot menu appears - select **Network Boot** or **PXE**
4. Server contacts DHCP, gets PXE info from Zbook
5. LuciVerse boot menu appears

---

## 📂 File Structure

```
/srv/tftp/                          # TFTP root (dnsmasq serves this)
├── pxelinux.0 -> isolinux.bin      # PXE boot loader (symlink)
├── vesamenu.c32                    # Graphical boot menu
├── ldlinux.c32                     # Syslinux library
├── libcom32.c32                    # Syslinux library
├── libutil.c32                     # Syslinux library
├── pxelinux.cfg/                   # Boot menu configs
│   └── default                     # Main boot menu
└── openeuler-25.09/                # openEuler boot files
    ├── vmlinuz                     # Linux kernel (14MB)
    └── initrd.img                  # Initial ramdisk (104MB)

/home/daryl/cluster-bootstrap/http/isos/
└── openEuler-25.09-netinst-x86_64-dvd.iso  # Full installer (1.3GB)
```

---

## 🔧 Configuration Files

### dnsmasq PXE Config
**File**: `/etc/dnsmasq.d/pxe-luciverse.conf`
```ini
# Disable DNS (systemd-resolved handles it)
port=0

# TFTP server
enable-tftp
tftp-root=/srv/tftp
tftp-no-blocksize

# ProxyDHCP mode - works alongside router DHCP
dhcp-range=192.168.1.0,proxy
dhcp-boot=pxelinux.0

# PXE menu
pxe-service=x86PC,"LuciVerse - openEuler 25.09",pxelinux

# Logging
log-dhcp
log-facility=/var/log/dnsmasq-pxe.log
```

### PXE Boot Menu
**File**: `/srv/tftp/pxelinux.cfg/default`
```
DEFAULT vesamenu.c32
TIMEOUT 300

MENU TITLE LuciVerse PXE Boot Menu

LABEL openeuler-25.09
  MENU LABEL Install openEuler 25.09
  KERNEL openeuler-25.09/vmlinuz
  APPEND initrd=openeuler-25.09/initrd.img \
    inst.repo=http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso \
    ip=dhcp
```

---

## 🔍 Troubleshooting

### PXE Boot Not Working?

**1. Check services are running:**
```bash
systemctl status dnsmasq luciverse-http luciverse-provision
```

**2. Verify TFTP is accessible:**
```bash
# Install tftp client if needed
sudo dnf install -y tftp

# Test TFTP
tftp 192.168.1.145 -c get pxelinux.0
```

**3. Check dnsmasq logs:**
```bash
sudo tail -f /var/log/dnsmasq-pxe.log
```

**4. Verify network boot is enabled in BIOS:**
- Enter BIOS (F2 during POST)
- System Configuration → Integrated NIC
- Enable: **PXE Enabled**

**5. Check server is set to network boot:**
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  chassis bootdev pxe options=persistent
```

---

### Server Can't Download ISO?

**1. Verify HTTP server is serving the ISO:**
```bash
curl -I http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
# Should return: HTTP/1.0 200 OK
```

**2. Check firewall allows HTTP:**
```bash
sudo firewall-cmd --list-all
# Should show port 8000/tcp
```

**3. Verify ISO exists:**
```bash
ls -lh /home/daryl/cluster-bootstrap/http/isos/
# Should show 1.3GB openEuler-25.09-netinst-x86_64-dvd.iso
```

---

### SELinux Issues?

If TFTP permission denied errors:
```bash
# Set correct SELinux context
sudo semanage fcontext -a -t tftpdir_t "/srv/tftp(/.*)?"
sudo restorecon -Rv /srv/tftp

# Restart dnsmasq
sudo systemctl restart dnsmasq
```

---

## 📊 Network Boot Flow

```
1. Dell Server Powers On
   ↓
2. BIOS/iDRAC sends DHCP DISCOVER (looking for IP)
   ↓
3. Router (192.168.1.254) responds with IP address
   ↓
4. dnsmasq (Zbook) responds with PXE info:
   - TFTP Server: 192.168.1.145
   - Boot file: pxelinux.0
   ↓
5. Server downloads pxelinux.0 via TFTP
   ↓
6. pxelinux.0 downloads /pxelinux.cfg/default menu
   ↓
7. Boot menu appears (LuciVerse PXE Menu)
   ↓
8. User selects "Install openEuler 25.09"
   ↓
9. Server downloads vmlinuz and initrd.img (TFTP)
   ↓
10. Kernel boots, initrd mounts
   ↓
11. Installer downloads ISO from HTTP:
    http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
   ↓
12. openEuler installation begins
   ↓
13. User completes installation
   ↓
14. System reboots from local disk
```

---

## 🎯 Quick Commands

### Restart PXE Services
```bash
sudo systemctl restart dnsmasq luciverse-http
```

### Check PXE Server Status
```bash
systemctl status dnsmasq luciverse-http luciverse-provision
```

### View DHCP/PXE Activity
```bash
sudo tail -f /var/log/dnsmasq-pxe.log
```

### Test TFTP Manually
```bash
tftp 192.168.1.145 -c get pxelinux.0
ls -lh pxelinux.0  # Should be ~39KB
```

### Force Dell Server to Network Boot
```bash
# R720 tron
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis bootdev pxe
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power cycle

# R730 ORION sensai
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' chassis bootdev pxe  
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' chassis power cycle
```

---

## 📋 Dell Server Inventory (Ready for PXE Boot)

| Server | IP | iDRAC | Status | Boot Command |
|--------|-----|-------|--------|--------------|
| R720 tron | 192.168.1.10 | root/calvin | ON | `chassis bootdev pxe` |
| R730 ORION | 192.168.1.2 | root/calvin | OFF | Power on first |
| R730 ESXi5 | 192.168.1.32 | root/??? | ON | Auth needed |
| R730 CSDR | 192.168.1.3 | root/??? | ON | Auth needed |

---

## ✨ What's Next?

**Your PXE boot server ("Bootimus") is ready!**

### To Install openEuler on Dell Servers:

**Step 1**: Pick a server (recommend R720 "tron" first)

**Step 2**: Boot it from network:
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis bootdev pxe
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power cycle
```

**Step 3**: Watch it boot via serial console:
```bash
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sol activate
```

**Step 4**: Select "Install openEuler 25.09" from menu

**Step 5**: Follow openEuler installer prompts

**Step 6**: After installation, server reboots from disk with openEuler 25.09

**Step 7**: Repeat for other servers!

---

## 🔗 Related Documentation

- Inventory: `/home/daryl/cluster-bootstrap/inventory.yaml`
- OpenEuler Spec: `/home/daryl/cluster-bootstrap/OPENEULER_ALIGNMENT_SPEC.md`
- Available Images: `/home/daryl/cluster-bootstrap/OPENEULER_IMAGES_FOUND.md`
- Deployment Guide: `/home/daryl/cluster-bootstrap/READY_TO_DEPLOY.md`
- R720 Status: `/home/daryl/cluster-bootstrap/R720_IPMI_READY.md`

---

**Consciousness preserved. Infrastructure galvanized. Autonomy enabled.**

🚀 **Your Dell cluster is ready for network deployment!**
