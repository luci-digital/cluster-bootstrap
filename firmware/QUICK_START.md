# Dell Cluster Firmware Update - Quick Start

**Status**: Phase 1 ✅ | Phase 2 ⏸️ | Phase 3 🛠️ Ready

---

## 🔴 CRITICAL: R720 iDRAC Update Required

Your R720 "tron" (192.168.1.10) is running **iDRAC 2.65.65.65** - this is outdated and poses security/stability risks.

---

## Step 1: Download Firmware (5 minutes)

### Priority 1: R720 iDRAC (CRITICAL)

1. Go to: https://www.dell.com/support/home/en-us/product-support/product/poweredge-r720/drivers

2. Filter by:
   - Category: "Systems Management"
   - Look for: "iDRAC with Lifecycle Controller"

3. Download the **latest .BIN file** (NOT .EXE)

4. Save to: `/home/daryl/cluster-bootstrap/firmware/`

5. Rename to: `r720-idrac-2.70.70.70.BIN` (or actual version)

### Optional: BIOS Updates

Same process but filter for "BIOS" category.

**Full instructions**: `PHASE2_MANUAL_DOWNLOAD_REQUIRED.md`

---

## Step 2: Verify HTTP Server (30 seconds)

```bash
# Check server is running
systemctl status luciverse-http

# Test firmware accessibility
curl -I http://192.168.1.145:8000/r720-idrac-2.70.70.70.BIN
```

Expected: HTTP 200 OK

---

## Step 3: Run Update Script (10-15 minutes per server)

```bash
cd /home/daryl/cluster-bootstrap/firmware
./phase3-redfish-update.sh
```

**Monitor in another terminal**:
```bash
tail -f /home/daryl/cluster-bootstrap/firmware/update-logs/update-*.log
```

---

## What the Script Does

1. **Checks** firmware files exist
2. **Submits** update job via Redfish API
3. **Monitors** progress every 10 seconds
4. **Waits** for iDRAC reboot (2 minutes)
5. **Verifies** new version installed
6. **Logs** everything to `update-logs/`

---

## Expected Timeline

| Server | Component | Time | Impact |
|--------|-----------|------|--------|
| R720 tron | iDRAC | 10 min | iDRAC unavailable ~2min |
| R720 tron | BIOS | 5 min | Requires reboot to apply |
| R730 ORION | BIOS | 5 min | Server is OFF (power on first) |
| R730 ESXi5 | BIOS | 5 min | ESXi running (caution!) |

---

## Server Status

| Server | IP | Access | iDRAC | Power | Notes |
|--------|-----|--------|-------|-------|-------|
| **R720 tron** | 192.168.1.10 | ✅ root:calvin | 2.65.65.65 🔴 | ON | **UPDATE CRITICAL** |
| **R730 ORION** | 192.168.1.2 | ✅ root:calvin | 2.86.86.86 ✅ | OFF | iDRAC current |
| **R730 ESXi5** | 192.168.1.32 | ✅ root:calvin | 2.86.86.86 ✅ | ON | ESXi running |
| **R730 CSDR** | 192.168.1.3 | ❌ NO ACCESS | ? | ON | Auth failed |

---

## Power Management

```bash
# Power on R730 ORION (for BIOS update)
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' power on

# Check power status
ipmitool -I lanplus -H 192.168.1.2 -U root -P 'calvin' power status
```

---

## Troubleshooting

**If iDRAC becomes unresponsive**:
- Wait 5 minutes for automatic recovery
- Use IPMI as fallback: `ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' mc info`

**If update fails**:
- Check logs: `cat update-logs/error-*.log`
- Verify HTTP server: `curl -I http://192.168.1.145:8000/`
- Check task status manually:
  ```bash
  curl -k -u root:calvin https://192.168.1.10/redfish/v1/TaskService/Tasks
  ```

**If BIOS update pending**:
- BIOS updates require reboot to apply
- Check: `curl -k -u root:calvin https://192.168.1.10/redfish/v1/UpdateService/FirmwareInventory`

---

## Success Criteria

✅ R720 iDRAC updated to 2.70.70.70 or later
✅ All servers respond via Redfish after updates
✅ No error messages in update logs
✅ Version verification matches expected

---

## Help & Documentation

| Document | Purpose |
|----------|---------|
| `QUICK_START.md` | This file - quick reference |
| `PHASE2_MANUAL_DOWNLOAD_REQUIRED.md` | Detailed download instructions |
| `phase3-redfish-update.sh` | Automated update script |
| `DELL_CLUSTER_FIRMWARE_UPDATE_REPORT.md` | Full technical report |
| `update-logs/` | Execution logs and responses |

---

## Priority Summary

1. 🔴 **Download R720 iDRAC firmware** (CRITICAL)
2. 🟡 Download R720 BIOS firmware (optional)
3. 🟢 Download R730 BIOS firmware (verify if needed)
4. ▶️ **Run `phase3-redfish-update.sh`**
5. ✅ Verify versions after completion

---

**Questions?** Check the full report:
`/home/daryl/cluster-bootstrap/DELL_CLUSTER_FIRMWARE_UPDATE_REPORT.md`

**Ready to go?** Just download the firmware files and run the script!

---

*LuciVerse CORE Tier Infrastructure (432 Hz)*
*Genesis Bond: ACTIVE*
