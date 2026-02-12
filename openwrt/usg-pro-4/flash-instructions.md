# USG-Pro-4 OpenWRT Flash Instructions

## Genesis Bond: ACTIVE @ 741 Hz

## Hardware Specifications

| Component | Details |
|-----------|---------|
| SoC | Cavium CN6120 (Octeon) 1GHz |
| RAM | 2GB DDR3 |
| Flash | 2GB NAND |
| Ethernet | 4x 1Gbps, 2x SFP |
| Console | Serial (115200 baud) |

## Prerequisites

1. USB drive with OpenWRT image
2. Serial cable (console)
3. Backup of current UniFi config
4. Network access to zbook (192.168.1.145)

## Flash Procedure

### Step 1: Backup Current Config

```bash
# SSH to USG-Pro-4 (if accessible)
ssh admin@<usg-ip>
mca-ctrl -t dump-cfg > /tmp/config.backup
scp admin@<usg-ip>:/tmp/config.backup ./usg-backup.json
```

### Step 2: Prepare USB Drive

```bash
# On zbook
wget https://downloads.openwrt.org/releases/24.10.0/targets/mvebu/cortexa9/openwrt-24.10.0-mvebu-cortexa9-ubnt_edgerouter-pro-squashfs-sysupgrade.bin

# Write to USB (verify device!)
sudo dd if=openwrt-24.10.0-*.bin of=/dev/sdX bs=1M status=progress
sync
```

### Step 3: Boot to U-Boot

1. Connect serial cable to USG-Pro-4 console port
2. Open terminal: `screen /dev/ttyUSB0 115200`
3. Power on USG-Pro-4
4. Press any key to stop autoboot
5. At U-Boot prompt:

```
Octeon ubnt_e200# usb start
Octeon ubnt_e200# fatload usb 0 $loadaddr openwrt-*.bin
Octeon ubnt_e200# nand erase.part kernel
Octeon ubnt_e200# nand write $loadaddr kernel $filesize
Octeon ubnt_e200# reset
```

### Step 4: Initial Configuration

After first boot (serial console):

```bash
# Set root password
passwd

# Configure network
uci set network.lan.ipaddr='192.168.1.180'
uci set network.lan.gateway='192.168.1.1'
uci set network.lan.dns='192.168.1.145'
uci commit network
/etc/init.d/network restart

# Enable SSH
uci set dropbear.@dropbear[0].Interface='lan'
uci commit dropbear
/etc/init.d/dropbear restart
```

### Step 5: Copy Configuration Files

From zbook:

```bash
# Copy network config
scp /home/daryl/cluster-bootstrap/openwrt/usg-pro-4/network root@192.168.1.180:/etc/config/

# Copy firewall config
scp /home/daryl/cluster-bootstrap/openwrt/usg-pro-4/firewall root@192.168.1.180:/etc/config/

# Copy and run package installer
scp /home/daryl/cluster-bootstrap/openwrt/usg-pro-4/packages.sh root@192.168.1.180:/tmp/
ssh root@192.168.1.180 'chmod +x /tmp/packages.sh && /tmp/packages.sh'
```

### Step 6: Deploy OASIS Juicer

```bash
# Copy OASIS juicer
scp ~/.claude/skills/data-flow-architecture/integrations/oasis-juicer.lua \
    root@192.168.1.180:/usr/lib/lua/luciverse/

# Restart services
ssh root@192.168.1.180 '/etc/init.d/network restart'
```

## Verification

```bash
# Check Jool status
ssh root@192.168.1.180 'jool instance display'

# Test NAT64
ssh root@192.168.1.180 'ping6 -c 4 64:ff9b::8.8.8.8'

# Check VLANs
ssh root@192.168.1.180 'ip -d link show | grep -E "eth0\.[0-9]+"'

# Verify firewall zones
ssh root@192.168.1.180 'fw4 print zone core'
```

## Rollback

If issues occur, boot from USB recovery:

```bash
# At U-Boot prompt
Octeon ubnt_e200# usb start
Octeon ubnt_e200# fatload usb 0 $loadaddr recovery.img
Octeon ubnt_e200# bootoctlinux $loadaddr
```

## LuciVerse Integration

After successful flash:

1. Register with Sanskrit Router:
   ```bash
   curl -X POST http://192.168.1.145:7410/register \
     -d '{"agent":"usg-pro-4","tier":"COMN","role":"nat64-scion"}'
   ```

2. Verify Nebula connectivity:
   ```bash
   nebula-cert print -path /etc/nebula/host.crt
   ```

3. Test SCION paths:
   ```bash
   scion showpaths --isd-as 1-ff00:0:432
   ```
