# ✅ Ready to Deploy - Dell Cluster OS Installation

**Status**: ALL ISOs READY
**Date**: 2026-01-27
**HTTP Server**: http://192.168.1.145:8000

---

## 📦 Available Installation Images

### 1. openEuler 25.09 (RECOMMENDED - Target Platform)
**URL**: `http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso`
**Size**: 1.3GB
**Type**: Network installer
**Matches**: OPENEULER_ALIGNMENT_SPEC.md ✅

### 2. NixOS 25.05 Minimal (Alternative)
**URL**: `http://192.168.1.145:8000/isos/nixos-minimal-25.05.806192.10e687235226-x86_64-linux.iso`
**Size**: 71MB
**Type**: Minimal installer
**Use case**: Quick bootstrap/PXE server

---

## 🚀 Deploy to Dell Servers

### R720 "tron" (192.168.1.10) - Bootstrap Server

**Method 1: iDRAC Web Interface**
1. Open: https://192.168.1.10 (credentials: root/calvin)
2. Virtual Console → Launch Virtual Console
3. Virtual Media → Map CD/DVD
4. Enter: `http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso`
5. Click "Map Device"
6. Reboot server

**Method 2: Command Line**
```bash
# Set boot device to virtual CD
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis bootdev cdrom

# Cycle power
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' chassis power cycle

# Access serial console
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sol activate
```

---

### R730 ORION "sensai" (192.168.1.2) - ML/COMN Node

**Status**: Currently powered OFF
**Asset Tag**: sensai (ML workload)

```bash
# 1. Power on
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' chassis power on

# 2. Wait 30 seconds for boot

# 3. Set virtual CD
# Open: https://192.168.1.2
# Map: http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso

# 4. Reboot to install
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' chassis power cycle

# 5. Monitor via SOL
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' sol activate
```

---

### R730 ESXi5 (192.168.1.32) - Currently Running VMware

**Decision Required**: 
- **Option A**: Keep VMware ESXi (no action)
- **Option B**: Replace with openEuler (wipes existing VMs!)

If choosing Option B:
```bash
# ⚠️ WARNING: This will WIPE all VMs on this host!

# 1. Backup any critical VMs first
# 2. Map ISO via https://192.168.1.32
# 3. Boot from virtual CD
```

---

### R730 CSDR282 (192.168.1.3) - Auth Issues

**Status**: iDRAC credentials unknown (root/calvin failed)
**Next Steps**:
1. Try web interface: https://192.168.1.3
2. Reset iDRAC password if needed
3. Then deploy same as other R730s

---

## 📋 Installation Checklist

For each server during installation:

### Network Configuration
- [ ] Static IP or DHCP? (Recommend static for servers)
- [ ] Hostname: Follow inventory (tron, sensai, etc.)
- [ ] DNS: 192.168.1.254 (gateway) or custom
- [ ] Gateway: 192.168.1.254

### Disk Configuration
- [ ] Partition layout (recommend: /, /boot, /home, swap)
- [ ] RAID configuration (if multiple disks)
- [ ] LVM or standard partitions?

### Software Selection
- [ ] Minimal install + Development Tools
- [ ] iSulad (container runtime) - per openEuler spec
- [ ] SSH server
- [ ] Git, vim, tmux (optional but useful)

### Post-Install (Per OPENEULER_ALIGNMENT_SPEC.md)
- [ ] Install k8s-install (Kubernetes)
- [ ] Configure A-Tune (system optimization)
- [ ] Setup oeAware (monitoring)
- [ ] Enable iSulad
- [ ] Configure Kuasar (multi-sandbox)
- [ ] Join to cluster network

---

## 🎯 Recommended Deployment Order

1. **R720 "tron"** (192.168.1.10)
   - Deploy first as bootstrap/provisioning server
   - Can become PXE server for others if needed
   - Already powered ON

2. **R730 ORION "sensai"** (192.168.1.2)
   - COMN tier node (528 Hz)
   - ML workload optimization
   - Currently OFF - needs power on

3. **R730 CSDR282** (192.168.1.3)
   - After resolving auth issues
   - General purpose node

4. **R730 ESXi5** (192.168.1.32)
   - Last (decision needed on ESXi migration)

---

## 🔧 Troubleshooting

### ISO won't mount in iDRAC
- Check HTTP server is running: `systemctl status luciverse-http`
- Verify URL is accessible: `curl -I http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso`
- Try local file mount instead of HTTP

### Server won't boot from virtual CD
- Check boot order in BIOS/iDRAC
- Ensure virtual media is enabled in iDRAC settings
- Try one-time boot menu (F11 during POST)

### Network installer can't reach repos
- Check server has internet connectivity
- Verify DNS resolution
- Try alternative mirror if needed

---

## 📞 Support Resources

- **openEuler Docs**: https://docs.openeuler.org/en/
- **Installation Guide**: https://docs.openeuler.org/en/docs/25.09/docs/Installation/installation.html
- **iDRAC User Guide**: Dell support site
- **Inventory File**: `/home/daryl/cluster-bootstrap/inventory.yaml`

---

## ✨ Next Step

**Start with R720 "tron"** - it's powered on and ready:

```bash
# Open iDRAC
open https://192.168.1.10

# Or start with serial console
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sol activate
```

Then map the ISO and reboot. Installation takes ~15-30 minutes.

🚀 **You're ready to deploy!**
