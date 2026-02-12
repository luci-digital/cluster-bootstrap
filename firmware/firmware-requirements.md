# Dell Cluster Firmware Requirements

## Discovery Summary (2026-01-27)

### R720 "tron" (192.168.1.10) - Service Tag: 4J0TV12
**Status**: 🔴 CRITICAL UPDATE NEEDED
- Current iDRAC: 2.65.65.65
- Target iDRAC: 2.82.82.82 or newer
- Current BIOS: 2.9.0
- Credentials: root/calvin ✓
- Priority: **HIGHEST**

**Required Files:**
- iDRAC: `iDRAC-with-Lifecycle-Controller_Firmware_XXX_LN_2.82.82.82_A00.BIN`
- BIOS: `BIOS_XXX_2.9.0.BIN` (already current)

### R730 ORION "sensai" (192.168.1.2) - Service Tag: CQ5QBM2
**Status**: ⚠️ BIOS UPDATE RECOMMENDED
- Current iDRAC: 2.86.86.86 ✓
- Current BIOS: 2.19.0
- Target BIOS: 2.20.0 or newer
- Power State: OFF
- Credentials: root/calvin ✓
- Priority: MEDIUM

**Required Files:**
- BIOS: `BIOS_XXX_2.20.0.BIN`

### R730 ESXi5 (192.168.1.32) - Service Tag: 1JD8Q22
**Status**: ⚠️ LC + BIOS UPDATE
- Current iDRAC: 2.86.86.86 ✓
- Current BIOS: 2.19.0
- Lifecycle Controller: 0.0 (UNUSUAL - needs investigation)
- Running: VMware ESXi
- Credentials: root/calvin ✓
- Priority: MEDIUM (ESXi requires careful handling)

**Required Files:**
- Lifecycle Controller: Check Dell support
- BIOS: `BIOS_XXX_2.20.0.BIN`

### R730 CSDR282 (192.168.1.3) - Service Tag: CSDR282
**Status**: ✓ UP TO DATE (BIOS unknown)
- Current iDRAC: 2.86.86.86 ✓
- BIOS: Not reported
- Credentials: root/Newdaryl24! ✓
- Priority: LOW

### R730 1JF6Q22 (192.168.1.31)
**Status**: ⚠️ BIOS UPDATE
- Current iDRAC: 2.86.86.86 ✓
- Current BIOS: 2.19.0
- Power State: OFF
- Credentials: root/calvin ✓
- Priority: MEDIUM

### R730 1JF7Q22 (192.168.1.33)
**Status**: ⚠️ BIOS UPDATE
- Current iDRAC: 2.86.86.86 ✓
- Current BIOS: 2.19.0
- Power State: OFF
- Credentials: root/Newdaryl24! ✓
- Priority: MEDIUM

## Firmware Download Links

### Dell Support Sites
- R720: https://www.dell.com/support/home/en-us/product-support/servicetag/4J0TV12
- R730 ORION: https://www.dell.com/support/home/en-us/product-support/servicetag/CQ5QBM2
- R730 ESXi5: https://www.dell.com/support/home/en-us/product-support/servicetag/1JD8Q22
- R730 CSDR: https://www.dell.com/support/home/en-us/product-support/servicetag/CSDR282
- R730 1JF6Q22: https://www.dell.com/support/home/en-us/product-support/servicetag/1JF6Q22
- R730 1JF7Q22: https://www.dell.com/support/home/en-us/product-support/servicetag/1JF7Q22

### Alternative: Dell Linux Repository
```bash
# Add Dell repository (if not blocked)
wget -q -O - https://linux.dell.com/repo/hardware/dsu/public.key | gpg --dearmor > /usr/share/keyrings/dell-repo.gpg

echo "deb [signed-by=/usr/share/keyrings/dell-repo.gpg] https://linux.dell.com/repo/hardware/dsu/os_independent/ /" > /etc/apt/sources.list.d/dell-dsu.list

# Search for firmware
apt-cache search idrac
apt-cache search bios | grep -i r730
```

### Manual Download Process
1. Visit Dell support page for each service tag
2. Navigate to Drivers & Downloads
3. Filter by: BIOS, iDRAC with Lifecycle Controller
4. Download latest compatible versions
5. Place in: `/home/daryl/cluster-bootstrap/firmware/`

## Update Order

### Phase 1: Critical (R720 iDRAC)
1. R720 tron - iDRAC update (CRITICAL - security + compatibility)

### Phase 2: Medium Priority (R730 BIOS)
2. R730 ORION - Power on, BIOS update
3. R730 1JF6Q22 - Power on, BIOS update
4. R730 1JF7Q22 - Power on, BIOS update

### Phase 3: ESXi Server (Careful)
5. R730 ESXi5 - Lifecycle Controller check, then BIOS update (coordinate with ESXi maintenance window)

### Phase 4: Verification
6. R730 CSDR282 - Verify BIOS version, update if needed

## Notes
- All R730s have current iDRAC firmware (2.86.86.86)
- R720 is running OLD iDRAC (2.65 from ~2016) - major security/stability risk
- ESXi server needs special care - update during maintenance window
- Servers powered OFF need to be powered on for BIOS updates (via IPMI)
- HTTP server ready at: http://192.168.1.145:8000/firmware/
