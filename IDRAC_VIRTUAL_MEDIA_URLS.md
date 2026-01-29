# iDRAC Virtual Media URLs - Domain Names Ready

**Issue Resolved**: Added DNS entries to /etc/hosts
**Test**: `ping bootimus.local` ✅ Works!

---

## ✅ Use These URLs in iDRAC Virtual Media

### For openEuler 25.09
```
http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
```

**Alternative hostnames** (all point to 192.168.1.145):
```
http://zboot.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
http://pxe.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
```

### For Bootimus FreeBSD 15.0 (when copied)
```
http://bootimus.local:8000/isos/bootimus-freebsd15.0-RELEASE-amd64-20260105.iso
```

### For NixOS 25.05
```
http://bootimus.local:8000/isos/nixos-minimal-25.05.806192.10e687235226-x86_64-linux.iso
```

---

## 📝 How to Use in iDRAC

### Step 1: Open iDRAC Web Interface
```bash
# R720 tron
https://192.168.1.10

# R730 ORION
https://192.168.1.2

# Login: root/calvin
```

### Step 2: Launch Virtual Console
1. Click **Virtual Console** in left menu
2. Click **Launch Virtual Console**
3. Java/HTML5 console opens

### Step 3: Map Virtual Media
In the virtual console window:
1. Click **Virtual Media** in top menu
2. Select **Map CD/DVD...**
3. Enter one of the URLs above
4. Click **Map Device**

### Step 4: Boot from Virtual CD
1. Reboot the server (or click **Boot to Virtual CD/DVD**)
2. Watch it boot from the ISO

---

## 🔧 Copy Bootimus ISO First (If You Want FreeBSD)

```bash
sudo cp /home/daryl/leaderhodes-workspace/luci-greenlight-012026/bootimus-freebsd15.0-RELEASE-amd64-20260105.iso \
  /home/daryl/cluster-bootstrap/http/isos/

# Verify it's accessible
curl -I http://bootimus.local:8000/isos/bootimus-freebsd15.0-RELEASE-amd64-20260105.iso
```

---

## 📊 Available ISOs

| ISO | Size | URL |
|-----|------|-----|
| **openEuler 25.09** | 1.3GB | http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso |
| **NixOS 25.05** | 71MB | http://bootimus.local:8000/isos/nixos-minimal-25.05.806192.10e687235226-x86_64-linux.iso |
| **Bootimus FreeBSD** | 291MB | *(copy first, then use URL above)* |

---

## 🚨 Troubleshooting

### If iDRAC Still Says "Invalid URL"

**Try without port**:
```
http://bootimus.local/isos/openEuler-25.09-netinst-x86_64-dvd.iso
```

**Or use IP address** (should work now):
```
http://192.168.1.145:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
```

### If Name Doesn't Resolve from Dell Server

The DNS entry is only on the Zbook. You may need to:
1. Use the IP address in iDRAC instead
2. OR access iDRAC from Zbook (where the DNS entry exists)

### HTTP Server Not Running?

```bash
systemctl status luciverse-http
# Should show: active (running)

# If not:
sudo systemctl start luciverse-http
```

### Can't Access from Browser?

Test from Zbook:
```bash
curl -I http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
# Should return: HTTP/1.0 200 OK
```

---

## 🎯 Quick Start: Boot R720 with openEuler

```bash
# 1. Open iDRAC
firefox https://192.168.1.10  # or your browser

# 2. Login: root/calvin

# 3. Virtual Console → Launch Virtual Console

# 4. Virtual Media → Map CD/DVD
# URL: http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso

# 5. Reboot server (or Boot to Virtual CD/DVD)

# 6. Watch serial console:
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' sol activate
```

---

## 📋 All Dell Servers

| Server | iDRAC IP | URL for Virtual Media |
|--------|----------|----------------------|
| **R720 tron** | 192.168.1.10 | https://192.168.1.10 |
| **R730 ORION** | 192.168.1.2 | https://192.168.1.2 |
| **R730 ESXi5** | 192.168.1.32 | https://192.168.1.32 |
| **R730 CSDR** | 192.168.1.3 | https://192.168.1.3 |

All can use:
```
http://bootimus.local:8000/isos/openEuler-25.09-netinst-x86_64-dvd.iso
```

---

**DNS Entries Added**: `bootimus.local`, `zboot.local`, `pxe.local` → 192.168.1.145

**Test**: `ping bootimus.local` ✅ Works!

🚀 **Ready to boot!**
