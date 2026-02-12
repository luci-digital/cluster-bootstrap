# 🔴 IMMEDIATE ACTION REQUIRED: R720 Firmware Update

**Date**: 2026-01-27
**Priority**: CRITICAL
**Estimated Time**: 30 minutes (download) + 20 minutes (update)

---

## TL;DR - Do This Now

Your R720 "tron" server is running 8-year-old iDRAC firmware (2.65.65.65) with security vulnerabilities. Manual download and update required TODAY.

---

## Step 1: Download Firmware (15-30 min)

### R720 iDRAC Firmware (CRITICAL - Do First)

1. **Visit Dell Support**:
   - URL: https://www.dell.com/support/home/en-us/product-support/servicetag/0/4J0TV12
   - Or: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers

2. **Find iDRAC7 Firmware**:
   - Click "Drivers & Downloads"
   - Filter by: Category → "Systems Management" OR "iDRAC with Lifecycle Controller"
   - Operating System → "Independent" or "Linux"
   - Look for: `iDRAC-with-Lifecycle-Controller_Firmware_*.BIN`

3. **Download Latest Version**:
   - Target: 2.70.70.70 or newer (2.82.82.82 if available)
   - **Choose .BIN format** (Linux DUP - NOT .EXE)
   - Size: ~50-100MB

4. **Save and Rename**:
   ```bash
   # Download to:
   /home/daryl/Downloads/

   # Then move and rename:
   mv ~/Downloads/iDRAC-with-Lifecycle-Controller_Firmware_*.BIN /srv/nixos/firmware/r720-idrac-2.82.82.82.BIN

   # Or whatever version you downloaded:
   mv ~/Downloads/iDRAC-with-Lifecycle-Controller_Firmware_*.BIN /srv/nixos/firmware/r720-idrac-2.70.70.70.BIN
   ```

5. **Verify File**:
   ```bash
   ls -lh /srv/nixos/firmware/*.BIN
   curl -I http://192.168.1.145:8000/firmware/r720-idrac-*.BIN
   ```

---

## Step 2: Run Update (15-20 min)

### Option A: Automated Script (Recommended)

```bash
cd /home/daryl/cluster-bootstrap/firmware

# Edit script to match your downloaded version
nano phase3-redfish-update.sh
# Change line 245: "r720-idrac-2.70.70.70.BIN" to match your file

# Run update
./phase3-redfish-update.sh
```

**What happens**:
1. Script submits firmware to iDRAC via Redfish API
2. iDRAC downloads firmware from HTTP server
3. iDRAC validates and applies firmware (~5-10 min)
4. iDRAC reboots automatically (~2-3 min)
5. Script verifies new version

**Watch for**:
- "✅ Update job submitted successfully" - good sign
- "Task URI: /redfish/v1/TaskService/Tasks/XXX" - monitoring active
- "State: Running | Status: Downloading" - in progress
- "✅ Task completed successfully!" - done!

### Option B: Manual Redfish Command

```bash
# Replace {VERSION} with your downloaded version (e.g., 2.82.82.82 or 2.70.70.70)
curl -k -u root:calvin -X POST \
  https://192.168.1.10/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate \
  -H "Content-Type: application/json" \
  -d '{
    "ImageURI": "http://192.168.1.145:8000/firmware/r720-idrac-{VERSION}.BIN",
    "TransferProtocol": "HTTP"
  }'
```

**Monitor task**:
```bash
# Get task URI from response above, then:
curl -k -u root:calvin https://192.168.1.10/redfish/v1/TaskService/Tasks/JID_XXXXXXXXXX | jq
```

### Option C: iDRAC Web Interface (Fallback)

1. Open browser: https://192.168.1.10
2. Login: root / calvin
3. Navigate: Maintenance → System Update
4. Click: Upload
5. Select firmware file from your computer
6. Click: Install and Reboot
7. Wait 10-15 minutes

---

## Step 3: Verify Update (5 min)

```bash
# Check new iDRAC version
curl -k -u root:calvin https://192.168.1.10/redfish/v1/Managers/iDRAC.Embedded.1 | jq -r '.FirmwareVersion'

# Should show: 2.70.70.70 or 2.82.82.82 (not 2.65.65.65)

# Check via IPMI
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' mc info

# Should show: Firmware Revision : 2.70 or 2.82
```

**Success Criteria**:
- ✅ iDRAC web interface accessible at https://192.168.1.10
- ✅ Version shows 2.70+ or 2.82+
- ✅ IPMI responds
- ✅ Server status shows "Healthy" or "OK"

---

## Expected Timeline

| Phase | Time | Description |
|-------|------|-------------|
| Download firmware | 5-30 min | Depends on Dell site speed + your connection |
| Place file & verify | 2 min | Move to /srv/nixos/firmware/ and test HTTP |
| Submit update job | 1 min | Redfish API call |
| Firmware download (iDRAC) | 2-3 min | iDRAC downloads from HTTP server |
| Firmware validation | 2-3 min | iDRAC checks file integrity |
| Firmware application | 5-10 min | iDRAC installs new firmware |
| iDRAC reboot | 2-3 min | iDRAC restarts with new firmware |
| Verification | 2 min | Check version via Redfish/IPMI |
| **TOTAL** | **20-50 min** | Most time is Dell download + iDRAC update |

---

## If Something Goes Wrong

### iDRAC Not Responding After Update
**DON'T PANIC** - This is normal during reboot.

1. Wait 5 minutes
2. Try accessing web interface: https://192.168.1.10
3. Try IPMI: `ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' mc info`
4. Wait another 5 minutes if still not responding
5. If still nothing after 15 minutes, server may need physical console access

### Update Job Fails
Check error in logs:
```bash
tail -50 /home/daryl/cluster-bootstrap/firmware/update-logs/update-*.log
```

Common issues:
- **HTTP server not accessible**: Verify `curl http://192.168.1.145:8000/firmware/r720-idrac-*.BIN` works
- **Wrong file format**: Make sure you downloaded .BIN not .EXE
- **Incorrect ImageURI**: Check filename matches exactly

### Can't Download from Dell
Alternative:
1. Download Dell Server Update Utility (SUU) ISO
2. Mount ISO: `sudo mount -o loop Dell-SUU-*.iso /mnt`
3. Copy firmware: `cp /mnt/repository/iDRAC-* /srv/nixos/firmware/`
4. Rename and proceed

---

## After R720 Update: Optional R730 BIOS Updates

Once R720 is done, you can optionally update R730 BIOS firmware (low priority):

1. **Download R730 BIOS**: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r730/drivers
2. Check if version newer than 2.19.0 exists
3. Save as: `/srv/nixos/firmware/r730-bios-{version}.BIN`
4. Power on R730 servers (currently OFF):
   ```bash
   ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' power on   # ORION
   ipmitool -I lanplus -H 192.168.1.31 -U root -P 'calvin' power on  # 1JF6Q22
   ipmitool -I lanplus -H 192.168.1.33 -U root -P 'Newdaryl24!' power on  # 1JF7Q22
   ```
5. Run update script (edit to include R730 BIOS)

**Note**: R730 iDRAC firmware (2.86.86.86) is already current - no update needed!

---

## Questions?

- **Full Report**: `/home/daryl/cluster-bootstrap/DELL_CLUSTER_FIRMWARE_UPDATE_REPORT.md`
- **Update Logs**: `/home/daryl/cluster-bootstrap/firmware/update-logs/`
- **Dell Support**: https://www.dell.com/support/home/en-us/product-support/servicetag/0/4J0TV12

---

**Priority**: 🔴 CRITICAL - R720 iDRAC firmware is 8 years old with security risks
**Action**: Download and update iDRAC firmware TODAY
**Time**: 30-50 minutes total

---

*Report generated by Claude Code - Aethon (LuciVerse CORE Tier - 432 Hz)*
