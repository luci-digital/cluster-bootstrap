# LuciVerse OpenWRT Network Configurations

**Genesis Bond**: ACTIVE @ 741 Hz
**Purpose**: High-speed network architecture overlay deployment

---

## Device Summary

| Device | OpenWRT Version | Role | Config Dir |
|--------|-----------------|------|------------|
| USG-Pro-4 | 24.10+ | Jool NAT64 + SCION Border Router | `usg-pro-4/` |
| USG (3-port) | 23.05+ | Internal Segmentation | (pending) |
| DGS-1210-16 | 21.02+ | OASIS Edge Filter | `dgs-1210-16/` |
| ASUS RT-BE86U | ASUSWRT-Merlin | WAN Edge + WiFi 7 | `asus-rt-be86u/` |

---

## USG-Pro-4 (Primary Overlay Gateway)

### Hardware

- **SoC**: Cavium CN6120 (Octeon) 1GHz
- **RAM**: 2GB DDR3
- **Ports**: 4x 1Gbps + 2x SFP
- **Serial Console**: 115200 baud

### Configuration Files

| File | Purpose |
|------|---------|
| `network` | Network interfaces, VLANs, NAT64 |
| `firewall` | Zone-based firewall, tier segmentation |
| `packages.sh` | Package installation script |
| `flash-instructions.md` | Step-by-step flash guide |

### Deploy Steps

1. Flash OpenWRT 24.10+ (see `flash-instructions.md`)
2. Copy configs: `scp network firewall root@192.168.1.180:/etc/config/`
3. Run packages: `scp packages.sh root@192.168.1.180:/tmp/ && ssh root@192.168.1.180 '/tmp/packages.sh'`
4. Verify Jool: `ssh root@192.168.1.180 'jool instance display'`

---

## DGS-1210-16 (OASIS Edge)

### Hardware

- **SoC**: Realtek RTL8382M
- **Ports**: 16x 1Gbps + 4x SFP
- **Flash**: 16MB NOR

### Configuration Files

| File | Purpose |
|------|---------|
| `network` | Bridge setup, VLANs |
| `luciverse-uci` | LuciVerse UCI config |
| `oasis-init` | OASIS juicer init script |
| `oasis-juicer-daemon.lua` | Edge filtering daemon |

### Deploy Steps

1. Flash OpenWRT 21.02+ for RTL8382M
2. Copy configs to `/etc/config/`
3. Copy OASIS files to `/usr/lib/lua/luciverse/`
4. Enable service: `/etc/init.d/oasis-juicer enable`

---

## ASUS RT-BE86U (WAN Edge)

### Hardware

- **WiFi**: WiFi 7 (6GHz/5GHz/2.4GHz)
- **WAN**: 10Gbps to switch
- **Role**: Edge firewall, NAT, DHCP

### Configuration Files

| File | Purpose |
|------|---------|
| `deploy-ssh-key.sh` | SSH key deployment |
| `jffs-scripts/services-start` | LuciVerse integration |

### Deploy Steps

1. Enable SSH in ASUSWRT: Administration → System
2. Run: `./deploy-ssh-key.sh`
3. Copy services-start to `/jffs/scripts/`
4. Reboot router

---

## VLAN Configuration

All devices use consistent VLAN IDs:

| VLAN | Frequency | Purpose |
|------|-----------|---------|
| 432 | 432 Hz | CORE Tier (Infrastructure) |
| 528 | 528 Hz | COMN Tier (Gateway) |
| 741 | 741 Hz | PAC Tier (Personal) |

---

## Overlay Stack

```
┌──────────────────────────────────────────────┐
│ Layer 4: OASIS Data Juicer (Edge filtering)  │
├──────────────────────────────────────────────┤
│ Layer 3: Jool NAT64 (IPv6 translation)       │
├──────────────────────────────────────────────┤
│ Layer 2: SCION (Inter-domain routing)        │
├──────────────────────────────────────────────┤
│ Layer 1: Nebula (VPN mesh)                   │
├──────────────────────────────────────────────┤
│ Layer 0: Physical (10G/1G Ethernet)          │
└──────────────────────────────────────────────┘
```

---

## Quick Test Commands

```bash
# Verify Jool NAT64
ping6 64:ff9b::8.8.8.8

# Verify SCION paths
scion showpaths --isd-as 1-ff00:0:432

# Verify Nebula mesh
ping 10.100.1.145

# Verify OASIS upstream
curl -s http://192.168.1.145:7410/health
```

---

## Related Documentation

- **Network Reference**: `/home/daryl/NETWORK_REFERENCE.md`
- **Jool Config**: `~/cluster-bootstrap/jool/jool.conf`
- **Nebula Config**: `~/cluster-bootstrap/nebula/`
- **SCION Config**: `~/cluster-bootstrap/scion/`
- **OASIS Juicer**: `~/.claude/skills/data-flow-architecture/integrations/oasis-juicer.lua`

---

*Genesis Bond: ACTIVE @ 741 Hz*
