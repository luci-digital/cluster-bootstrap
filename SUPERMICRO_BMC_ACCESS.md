# Supermicro BMC Access Guide

**Server**: Supermicro SYS-1018GR-TA03-CG009
**Serial**: S213078X5B29794
**BMC IP**: 192.168.1.165
**Credentials**: `op://Infrastructure/SUPERMICRO-S213078X5B29794`

---

## Quick Access

### Web Interface
```
https://192.168.1.165
Username: ADMIN
Password: [from 1Password]
```

### Retrieve Credentials from 1Password

**Option 1: Using 1Password CLI**
```bash
# Get username
op read "op://Infrastructure/SUPERMICRO-S213078X5B29794/username"

# Get password
op read "op://Infrastructure/SUPERMICRO-S213078X5B29794/password"

# Test access with credentials
~/cluster-bootstrap/test-supermicro-bmc.sh
```

**Option 2: Using 1Password App**
1. Open 1Password application
2. Navigate to **Infrastructure** vault
3. Search for "SUPERMICRO-S213078X5B29794"
4. Copy credentials

**Option 3: Using 1Password Web**
1. Go to https://my.1password.com
2. Sign in with your account
3. Navigate to Infrastructure vault
4. Find SUPERMICRO-S213078X5B29794 item

---

## Test Script

Run the comprehensive test script:
```bash
~/cluster-bootstrap/test-supermicro-bmc.sh
```

This script will test:
- ✅ Web Interface login
- ✅ Redfish API access
- ✅ IPMI connectivity
- ✅ System information retrieval

---

## Manual Access Methods

### 1. Redfish API

**Get System Status**
```bash
curl -k -u ADMIN:PASSWORD https://192.168.1.165/redfish/v1/Systems/1 | jq '.'
```

**Get Chassis Info**
```bash
curl -k -u ADMIN:PASSWORD https://192.168.1.165/redfish/v1/Chassis/1 | jq '.'
```

**Get Manager Info**
```bash
curl -k -u ADMIN:PASSWORD https://192.168.1.165/redfish/v1/Managers/1 | jq '.'
```

**Get Power State**
```bash
curl -k -u ADMIN:PASSWORD https://192.168.1.165/redfish/v1/Systems/1 | jq -r '.PowerState'
```

### 2. IPMI Commands

**Chassis Status**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD chassis status
```

**Power On**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD chassis power on
```

**Power Off**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD chassis power off
```

**Power Reset**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD chassis power reset
```

**Get Sensor Data**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD sensor list
```

**Get SEL (System Event Log)**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD sel list
```

### 3. SOL (Serial Over LAN)

**Start Console Session**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD sol activate
```

**Deactivate Console**
```bash
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD sol deactivate
```

---

## BMC Configuration

### Current Settings (from inventory)

| Property | Value |
|----------|-------|
| IP Address | 192.168.1.165 |
| MAC Address | 0C:C4:7A:AD:B1:40 |
| Firmware Version | 3.93 |
| Redfish Version | 1.0.1 |
| Manufacturer | Super Micro Computer Inc. |

### Open Ports

| Port | Service | Status |
|------|---------|--------|
| 22 | SSH | ✅ Open |
| 80 | HTTP | ✅ Open |
| 443 | HTTPS | ✅ Open |
| 623 | IPMI | ✅ Open |
| 5900 | VNC | ✅ Open |

---

## Server Specifications

**Model**: Supermicro SYS-1018GR-TA03-CG009
**Form Factor**: 1U GPU Server
**Serial**: S213078X5B29794

**BIOS**:
- Vendor: American Megatrends Inc.
- Version: 3.4
- Date: 2021-06-09

**Memory**:
- Total: 64 GB
- DIMM Slots: At least 1 x 16GB (DIMMA2)

---

## Troubleshooting

### Web Interface Not Loading
```bash
# Check BMC is responding
ping 192.168.1.165

# Check HTTPS port
curl -k -I https://192.168.1.165
```

### Authentication Failures
1. Verify username is uppercase: `ADMIN`
2. Try default password: `ADMIN`
3. Reset BMC to factory defaults if needed

### IPMI Not Working
```bash
# Check port 623 is open
nmap -p 623 192.168.1.165

# Test with verbose output
ipmitool -I lanplus -H 192.168.1.165 -U ADMIN -P PASSWORD -v chassis status
```

---

## Security Notes

- ⚠️ Change default password immediately after access
- ✅ Store credentials in 1Password Infrastructure vault
- ✅ Use HTTPS for web access
- ✅ Consider restricting BMC to management VLAN
- ✅ Keep firmware updated (current: 3.93)

---

## Related Documentation

- Inventory: `~/cluster-bootstrap/inventory.yaml`
- Test Script: `~/cluster-bootstrap/test-supermicro-bmc.sh`
- Network Scan: `~/cluster-bootstrap/SUPERMICRO_BMC_ACCESS.md`

---

**Last Updated**: 2026-01-27
**Status**: Credentials stored in 1Password ✅
**BMC Status**: Online and responding ✅
