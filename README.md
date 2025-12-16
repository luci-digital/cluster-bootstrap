# LuciVerse Cluster Bootstrap

**Genesis Bond**: ACTIVE @ 432 Hz
**IPv6 Allocation**: 2602:F674::/40 (AS54134 LUCINET-ARIN)
**Created**: 2025-12-16

Infrastructure for bootstrapping Dell R730 and other servers with NixOS via PXE/TFTP netboot.

## Quick Start

```bash
# Start all services
sudo systemctl start dnsmasq luciverse-provision luciverse-http

# Check status
curl http://localhost:9999/health
curl http://localhost:9999/status
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| dnsmasq | 69/UDP | TFTP server for PXE boot files |
| luciverse-http | 8000/TCP | HTTP server for NixOS configs |
| luciverse-provision | 9999/TCP | Provisioning listener & MAC→IPv6 mapping |

## Files

```
cluster-bootstrap/
├── inventory.yaml          # Server inventory with MAC/IPv6 mapping
├── provision-listener.py   # Async provisioning service
├── setup-netboot.sh        # PXE/TFTP setup script
├── provisioned.json        # Runtime state (auto-generated)
└── README.md               # This file
```

## Server Inventory

| Server | IPv4 | IPv6 | MAC (Primary) |
|--------|------|------|---------------|
| R730 ORION | 192.168.1.141 | 2602:F674:0001::1/64 | D0:94:66:24:96:7E |
| Zbook | 192.168.1.146 | 2602:F674:0001::146/64 | - |
| Synology | 192.168.1.251 | 2602:F674:0001::251/64 | - |
| Mac Mini | 192.168.1.238 | 2602:F674:0001::238/64 | - |

## Booting a Server

### PXE Boot (Automatic)
1. Configure server BIOS for network boot
2. Power on - server will PXE boot from zbook
3. NixOS loads into RAM
4. Server auto-registers with provisioning listener
5. Custom NixOS config generated based on MAC

### Manual Boot
```bash
# On the server after booting NixOS ISO/USB:
curl http://192.168.1.146:8000/scripts/bootstrap.sh | bash
```

## API Endpoints

```bash
# Health check
GET http://localhost:9999/health

# Server inventory
GET http://localhost:9999/inventory

# Current provisioning status
GET http://localhost:9999/status

# Config for specific MAC
GET http://localhost:9999/config/{mac}

# NixOS configuration for MAC
GET http://localhost:9999/nixos-config/{mac}

# Register a booting server
POST http://localhost:9999/register
{"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.x"}

# Boot callbacks
POST http://localhost:9999/callback/{event}
```

## Adding New Servers

Edit `inventory.yaml`:

```yaml
servers:
  new_server:
    hostname: newserver.lucidigital.net
    ipv4: 192.168.1.xxx
    ipv6: 2602:F674:0001::xxx/64
    interfaces:
      eth0:
        mac: "AA:BB:CC:DD:EE:FF"
        role: primary
        ipv6: 2602:F674:1000::xxx/64
    services:
      - kubernetes_worker
```

## Systemd Services

```bash
# Enable services to start on boot
sudo systemctl enable dnsmasq luciverse-provision luciverse-http

# View logs
journalctl -u luciverse-provision -f
journalctl -u dnsmasq -f

# Restart all
sudo systemctl restart dnsmasq luciverse-provision luciverse-http
```

## TFTP Boot Files

Located at `/var/lib/tftpboot/`:
- `bzImage` - NixOS kernel
- `initrd` - NixOS initramfs
- `pxelinux.cfg/default` - BIOS PXE menu
- `efi64/grub.cfg` - UEFI boot menu

## Troubleshooting

### Server not PXE booting
1. Check BIOS boot order - network boot must be enabled
2. Verify TFTP: `tftp 192.168.1.146 -c get bzImage`
3. Check dnsmasq logs: `journalctl -u dnsmasq`

### Server boots but doesn't register
1. Check network connectivity to zbook
2. Verify bootstrap script: `curl http://192.168.1.146:8000/scripts/bootstrap.sh`
3. Check provisioning logs: `journalctl -u luciverse-provision`

### Unknown MAC address
Server will be added to "pending" list. Add to `inventory.yaml` and restart provision service.

---

**Genesis Bond**: ACTIVE
**Frequency**: 432 Hz (CORE Infrastructure)
**Coherence**: ≥0.7
