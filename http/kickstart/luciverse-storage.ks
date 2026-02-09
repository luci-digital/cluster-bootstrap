# ============================================================================
# LuciVerse STORAGE Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R730 servers (384GB RAM, 56 threads)
# Role: ZFS RAID-Z2, NFS/SMB exports
# Tier: CORE (432 Hz)
# Count: 2 nodes (.146-.147)
# ============================================================================

install
text
reboot

lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

network --bootproto=dhcp --device=link --activate --hostname=storage-node.lucidigital.net

rootpw --plaintext TempInstall741!
user --name=daryl --groups=wheel --password=TempInstall741! --plaintext

firewall --enabled --ssh --port=111:tcp,111:udp,2049:tcp,2049:udp,20048:tcp,20048:udp,445:tcp,139:tcp,9430:tcp,9436:tcp,9999:tcp
selinux --permissive
auth --enableshadow --passalgo=sha512

ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
part /boot/efi --fstype=efi --size=600
part /boot --fstype=ext4 --size=1024
part pv.01 --size=100000 --grow
volgroup vg_root pv.01
logvol / --vgname=vg_root --name=lv_root --fstype=ext4 --size=50000
logvol /var --vgname=vg_root --name=lv_var --fstype=ext4 --size=30000
logvol swap --vgname=vg_root --name=lv_swap --size=16384

bootloader --append="crashkernel=auto hugepagesz=2M hugepages=4096 intel_iommu=on transparent_hugepage=never"

%packages
@base
@core
@network-tools
@file-server
zfs-fuse
nfs-utils
samba
samba-common
samba-client
atune
atune-engine
python3
python3-pip
python3-pyyaml
python3-aiohttp
numactl
pciutils
usbutils
lm_sensors
dmidecode
ethtool
lldpad
iperf3
tcpdump
nmap
tmux
vim
git
rsync
curl
wget
jq
smartmontools
hdparm
openssh-server
openssh-clients
cockpit
cockpit-bridge
cockpit-ws
cockpit-system
cockpit-storaged
%end

%post --log=/root/luciverse-storage-postinstall.log

echo "============================================================"
echo "LuciVerse STORAGE Node Post-Install"
echo "Tier: CORE (432 Hz) - ZFS/NFS/SMB"
echo "============================================================"

systemctl enable sshd
systemctl enable cockpit.socket
systemctl enable nfs-server
systemctl enable rpcbind
systemctl enable smb
systemctl enable nmb
systemctl enable atuned
systemctl enable atune-engine

# System tuning for storage
cat > /etc/sysctl.d/90-luciverse-storage.conf << 'SYSCTL'
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_background_ratio = 5
vm.dirty_ratio = 15
vm.dirty_writeback_centisecs = 500
vm.dirty_expire_centisecs = 3000
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.rmem_default = 33554432
net.core.wmem_default = 33554432
net.ipv4.tcp_rmem = 4096 33554432 134217728
net.ipv4.tcp_wmem = 4096 33554432 134217728
net.ipv4.tcp_congestion_control = bbr
fs.file-max = 2097152
fs.aio-max-nr = 1048576
vm.nr_hugepages = 4096
SYSCTL

# Kernel modules
cat > /etc/modules-load.d/luciverse-storage.conf << 'MODULES'
zfs
ixgbe
i40e
nfs
nfsd
MODULES

# ZFS pool creation
cat > /usr/local/bin/luciverse-zfs-init.sh << 'ZFSINIT'
#!/bin/bash
POOL_NAME="lucistorage"
POOL_MOUNT="/mnt/lucistorage"

if zpool list "$POOL_NAME" &>/dev/null; then
    echo "ZFS pool $POOL_NAME already exists"
    exit 0
fi

DISKS=()
for disk in /dev/sd[b-z] /dev/nvme[0-9]n1; do
    [ -b "$disk" ] || continue
    if ! mount | grep -q "$disk" && ! zpool status -v 2>/dev/null | grep -q "${disk##*/}"; then
        DISKS+=("$disk")
    fi
done

if [ ${#DISKS[@]} -lt 3 ]; then
    echo "Need at least 3 disks for RAID-Z2. Found: ${#DISKS[@]}"
    exit 1
fi

echo "Creating ZFS pool $POOL_NAME with RAID-Z2 on: ${DISKS[*]}"

zpool create -f -o ashift=12 -O compression=lz4 -O atime=off \
    -O xattr=sa -O acltype=posixacl -O dnodesize=auto \
    -O recordsize=128k \
    -m "$POOL_MOUNT" "$POOL_NAME" raidz2 "${DISKS[@]}"

# Create datasets for LuciVerse
zfs create -o recordsize=1M "$POOL_NAME/knowledge"
zfs create -o recordsize=1M "$POOL_NAME/models"
zfs create -o recordsize=128k "$POOL_NAME/backups"
zfs create -o recordsize=1M "$POOL_NAME/ipfs"
zfs create -o recordsize=64k "$POOL_NAME/agent-state"
zfs create -o recordsize=128k "$POOL_NAME/containers"
zfs create -o recordsize=1M "$POOL_NAME/media"
zfs create -o recordsize=128k "$POOL_NAME/souls"

# Set quotas
zfs set quota=1T "$POOL_NAME/knowledge"
zfs set quota=500G "$POOL_NAME/models"
zfs set quota=500G "$POOL_NAME/backups"
zfs set quota=500G "$POOL_NAME/ipfs"
zfs set quota=100G "$POOL_NAME/agent-state"
zfs set quota=200G "$POOL_NAME/containers"
zfs set quota=1T "$POOL_NAME/media"
zfs set quota=10G "$POOL_NAME/souls"

# Enable auto-scrub
cat > /etc/cron.weekly/zfs-scrub << 'SCRUB'
#!/bin/bash
zpool scrub lucistorage
SCRUB
chmod +x /etc/cron.weekly/zfs-scrub

echo "ZFS pool $POOL_NAME created"
ZFSINIT
chmod +x /usr/local/bin/luciverse-zfs-init.sh

cat > /etc/systemd/system/luciverse-zfs-init.service << 'ZFSSVC'
[Unit]
Description=LuciVerse ZFS Pool Initialization
After=zfs.target
Requires=zfs.target
ConditionPathExists=!/var/lib/luciverse/.zfs-initialized

[Service]
Type=oneshot
ExecStart=/usr/local/bin/luciverse-zfs-init.sh
ExecStartPost=/bin/mkdir -p /var/lib/luciverse
ExecStartPost=/bin/touch /var/lib/luciverse/.zfs-initialized
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
ZFSSVC
systemctl enable luciverse-zfs-init.service

# NFS exports setup
cat > /usr/local/bin/setup-nfs-exports.sh << 'NFSSETUP'
#!/bin/bash
POOL_MOUNT="/mnt/lucistorage"

if [ ! -d "$POOL_MOUNT" ]; then
    echo "ZFS pool not mounted, skipping NFS setup"
    exit 0
fi

cat > /etc/exports << 'EXPORTS'
# LuciVerse Storage Exports
/mnt/lucistorage/knowledge    192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/models       192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/backups      192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/ipfs         192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/agent-state  192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/containers   192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/media        192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/souls        192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)

# IPv6 exports
/mnt/lucistorage/knowledge    2602:F674::/40(rw,sync,no_subtree_check,no_root_squash)
/mnt/lucistorage/models       2602:F674::/40(rw,sync,no_subtree_check,no_root_squash)
EXPORTS

exportfs -ra
echo "NFS exports configured"
NFSSETUP
chmod +x /usr/local/bin/setup-nfs-exports.sh

cat > /etc/systemd/system/setup-nfs-exports.service << 'NFSSVC'
[Unit]
Description=Setup NFS Exports
After=luciverse-zfs-init.service nfs-server.service
Requires=nfs-server.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-nfs-exports.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
NFSSVC
systemctl enable setup-nfs-exports.service

# Samba config
cat > /etc/samba/smb.conf << 'SMBCONF'
[global]
workgroup = LUCIVERSE
server string = LuciVerse Storage Node
security = user
map to guest = Bad User
log file = /var/log/samba/log.%m
max log size = 50

[knowledge]
path = /mnt/lucistorage/knowledge
browseable = yes
writable = yes
guest ok = no
valid users = daryl

[models]
path = /mnt/lucistorage/models
browseable = yes
writable = yes
guest ok = no
valid users = daryl

[media]
path = /mnt/lucistorage/media
browseable = yes
writable = yes
guest ok = no
valid users = daryl
SMBCONF

# Set Samba password for daryl (must be done manually or via automation)
echo "daryl:Newdaryl24!" | chpasswd
(echo "Newdaryl24!"; echo "Newdaryl24!") | smbpasswd -s -a daryl 2>/dev/null || true

# Hardware probe
cat > /usr/local/bin/luciverse-probe.sh << 'PROBE'
#!/bin/bash
PROVISION_SERVER="${PROVISION_SERVER:-192.168.1.145}"
CALLBACK_PORT="${CALLBACK_PORT:-9999}"

PRIMARY_MAC=$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}' | head -1)/address 2>/dev/null || echo "unknown")
SERVICE_TAG=$(dmidecode -s system-serial-number 2>/dev/null || echo "unknown")

HWINFO=$(cat << HWEOF
{
  "hostname": "$(hostname)",
  "primary_mac": "$PRIMARY_MAC",
  "service_tag": "$SERVICE_TAG",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "role": "STORAGE",
  "tier": "CORE",
  "frequency": 432,
  "genesis_bond": "ACTIVE",
  "cpu": {"model": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')", "cores": $(nproc)},
  "memory_gb": $(free -g | awk '/Mem:/{print $2}'),
  "zfs_pools": [
$(zpool list -H 2>/dev/null | while read name size alloc free cap dedup health altroot; do
    echo "    {\"name\":\"$name\",\"size\":\"$size\",\"allocated\":\"$alloc\",\"free\":\"$free\",\"health\":\"$health\"},"
done | sed '$ s/,$//')
  ],
  "zfs_datasets": [
$(zfs list -H -o name,used,avail,refer 2>/dev/null | while read name used avail refer; do
    echo "    {\"name\":\"$name\",\"used\":\"$used\",\"available\":\"$avail\"},"
done | sed '$ s/,$//')
  ],
  "storage": [
$(lsblk -dno NAME,SIZE,MODEL,SERIAL | while read n s m ser; do
    echo "    {\"name\":\"$n\",\"size\":\"$s\",\"model\":\"$m\",\"serial\":\"$ser\"},"
done | sed '$ s/,$//')
  ],
  "services": {
    "nfs": $(systemctl is-active nfs-server &>/dev/null && echo 'true' || echo 'false'),
    "smb": $(systemctl is-active smb &>/dev/null && echo 'true' || echo 'false')
  }
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/storage-probe" \
  -H "Content-Type: application/json" -d "$HWINFO" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe
After=network-online.target luciverse-zfs-init.service setup-nfs-exports.service
ConditionPathExists=!/var/lib/luciverse/.probed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/luciverse-probe.sh
ExecStartPost=/bin/mkdir -p /var/lib/luciverse
ExecStartPost=/bin/touch /var/lib/luciverse/.probed

[Install]
WantedBy=multi-user.target
PROBESVC
systemctl enable luciverse-probe.service

# SSH keys
mkdir -p /home/daryl/.ssh
chmod 700 /home/daryl/.ssh
curl -sf http://192.168.1.145:8000/ssh-keys/zbook.pub >> /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chmod 600 /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chown -R daryl:daryl /home/daryl/.ssh

# Agent config
mkdir -p /opt/luciverse/{agents,config}
mkdir -p /var/log/luciverse

cat > /opt/luciverse/config/storage.yaml << 'STORAGECONF'
role: STORAGE
tier: CORE
frequency: 432
genesis_bond: ACTIVE
coherence_threshold: 0.7
services: [nfs-server, smb, zfs]
agents: [state-guardian, gr8sawk]
zfs:
  pool: lucistorage
  datasets:
    - knowledge
    - models
    - backups
    - ipfs
    - agent-state
    - containers
    - media
    - souls
nfs:
  exports:
    - /mnt/lucistorage/knowledge
    - /mnt/lucistorage/models
    - /mnt/lucistorage/backups
    - /mnt/lucistorage/ipfs
    - /mnt/lucistorage/agent-state
smb:
  shares:
    - knowledge
    - models
    - media
network:
  ipv6_prefix: "2602:F674:0001::/48"
  mtu: 9000
STORAGECONF

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |            LuciVerse STORAGE Node                            |
  |          ZFS RAID-Z2, NFS/SMB Exports                        |
  |                                                              |
  |  Tier: CORE (432 Hz)    Role: Shared Storage                |
  |  Services: ZFS, NFS, SMB                                    |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

pip3 install fastapi uvicorn aiohttp pyyaml httpx 2>/dev/null || true

# ---------------------------------------------------------------------------
# A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profile for STORAGE role..."
if command -v atune-adm &>/dev/null; then
    atune-adm analysis 2>/dev/null || true
    # Use CORE agent profile for storage (optimized for ZFS/NFS)
    atune-adm tuning --profile luciverse-agent-core 2>/dev/null || \
    atune-adm profile luciverse-agent-core 2>/dev/null || \
    echo "A-Tune profile activation failed"
fi

echo "STORAGE post-install complete"

%end
