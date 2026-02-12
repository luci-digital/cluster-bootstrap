# ============================================================================
# LuciVerse FABRIC Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R730 servers (384GB RAM, 56 threads, PERC H730)
# Role: iSulad containers, IPFS datastore, ZFS fabric
# Tier: CORE (432 Hz)
# Count: 3 nodes (.140-.142)
# ============================================================================

# Install mode
install
text
reboot

# Language and keyboard
lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

# Network - DHCP during install, static IPv6 configured in %post
network --bootproto=dhcp --device=link --activate --hostname=fabric-node.lucidigital.net

# Root password (temporary - will be updated from 1Password in %post)
# Real credentials fetched from provision-listener's 1Password Connect API
rootpw --plaintext TempInstall741!

# User account
user --name=daryl --groups=wheel --password=TempInstall741! --plaintext

# Security
firewall --enabled --ssh --port=4001:tcp,4001:udp,5001:tcp,8080:tcp,9430:tcp,9431:tcp,9432:tcp,9999:tcp
selinux --permissive
auth --enableshadow --passalgo=sha512

# Storage - Boot on first disk (LVM), ZFS pool created in %post
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

# Bootloader with CORE tier optimizations
bootloader --append="crashkernel=auto hugepagesz=2M hugepages=4096 intel_iommu=on iommu=pt transparent_hugepage=never"

# Package selection - FABRIC role
%packages
@base
@core
@network-tools
iSulad
isula-build
crun
fuse
fuse-libs
zfs-fuse
rdma-core
libibverbs
libibverbs-utils
librdmacm
librdmacm-utils
infiniband-diags
perftest
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
openssh-server
openssh-clients
cockpit
cockpit-bridge
cockpit-ws
cockpit-system
cockpit-storaged
# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh fabric
%end

# ============================================================================
# Post-install: Configure FABRIC node
# ============================================================================

%post --log=/root/luciverse-fabric-postinstall.log

echo "============================================================"
echo "LuciVerse FABRIC Node Post-Install Configuration"
echo "Tier: CORE (432 Hz)"
echo "Role: iSulad + IPFS + ZFS Fabric"
echo "============================================================"

# ---------------------------------------------------------------------------
# 0. Credential Injection from 1Password Connect
# ---------------------------------------------------------------------------
echo "Fetching credentials from 1Password Connect..."
curl -sf http://192.168.1.145:8000/scripts/credential-inject.sh | bash || \
    echo "Credential injection skipped - will use default passwords"

# ---------------------------------------------------------------------------
# 0.5 Overlay Network Bootstrap (Nebula + SCION)
# ---------------------------------------------------------------------------
echo "Bootstrapping overlay network certificates..."
curl -sf http://192.168.1.145:8000/scripts/overlay-bootstrap.sh | bash || \
    echo "Overlay network bootstrap skipped - will configure manually"

# ---------------------------------------------------------------------------
# 1. Enable essential services
# ---------------------------------------------------------------------------

systemctl enable sshd
systemctl enable cockpit.socket
systemctl enable isulad
systemctl enable lldpad
systemctl enable atuned
systemctl enable atune-engine

# ---------------------------------------------------------------------------
# 2. System tuning for FABRIC role
# ---------------------------------------------------------------------------

cat > /etc/sysctl.d/90-luciverse-fabric.conf << 'SYSCTL'
# LuciVerse FABRIC - ZFS/IPFS/Container optimizations

vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.core.rmem_default = 16777216
net.core.wmem_default = 16777216
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 65535
net.ipv4.tcp_rmem = 4096 16777216 67108864
net.ipv4.tcp_wmem = 4096 16777216 67108864
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_congestion_control = bbr
fs.file-max = 2097152
fs.inotify.max_user_watches = 1048576
vm.nr_hugepages = 4096
SYSCTL

# ---------------------------------------------------------------------------
# 3. Load kernel modules
# ---------------------------------------------------------------------------

cat > /etc/modules-load.d/luciverse-fabric.conf << 'MODULES'
ib_core
ib_uverbs
rdma_cm
rdma_ucm
ixgbe
i40e
fuse
bridge
br_netfilter
8021q
zfs
MODULES

# ---------------------------------------------------------------------------
# 4. iSulad configuration
# ---------------------------------------------------------------------------

mkdir -p /etc/isulad
cat > /etc/isulad/daemon.json << 'ISULAD'
{
  "group": "isula",
  "default-runtime": "lcr",
  "storage-driver": "overlay2",
  "storage-opts": ["overlay2.override_kernel_check=true"],
  "registry-mirrors": ["https://registry.lucidigital.net"],
  "insecure-registries": ["192.168.1.146:5050"],
  "native.umask": "secure",
  "log-driver": "json-file",
  "log-opts": {"max-size": "100m", "max-file": "3"},
  "cgroup-parent": "/luciverse",
  "pod-sandbox-image": "registry.lucidigital.net/pause:3.9",
  "cni-bin-dir": "/opt/cni/bin",
  "cni-conf-dir": "/etc/cni/net.d"
}
ISULAD

# ---------------------------------------------------------------------------
# 5. Install IPFS (kubo)
# ---------------------------------------------------------------------------

IPFS_VERSION="v0.26.0"
IPFS_URL="https://dist.ipfs.tech/kubo/${IPFS_VERSION}/kubo_${IPFS_VERSION}_linux-amd64.tar.gz"

mkdir -p /opt/ipfs
curl -L "$IPFS_URL" | tar -xz -C /opt/ipfs --strip-components=1 || echo "IPFS download failed, will retry"

if [ -f /opt/ipfs/ipfs ]; then
    ln -sf /opt/ipfs/ipfs /usr/local/bin/ipfs
    mkdir -p /var/lib/ipfs
    export IPFS_PATH=/var/lib/ipfs
    /opt/ipfs/ipfs init --profile server || true

    cat > /etc/systemd/system/ipfs.service << 'IPFSSVC'
[Unit]
Description=IPFS Daemon (FABRIC Node)
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
Environment="IPFS_PATH=/var/lib/ipfs"
ExecStart=/usr/local/bin/ipfs daemon --migrate
ExecStop=/bin/kill -s SIGINT $MAINPID
Restart=on-failure
RestartSec=10
User=root
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
IPFSSVC
    systemctl enable ipfs.service
fi

# ---------------------------------------------------------------------------
# 6. ZFS pool creation script
# ---------------------------------------------------------------------------

cat > /usr/local/bin/luciverse-zfs-init.sh << 'ZFSINIT'
#!/bin/bash
POOL_NAME="lucifabric"
POOL_MOUNT="/mnt/lucifabric"

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

if [ ${#DISKS[@]} -lt 2 ]; then
    echo "Need at least 2 disks for RAID-Z. Found: ${#DISKS[@]}"
    exit 1
fi

echo "Creating ZFS pool $POOL_NAME with RAID-Z2 on: ${DISKS[*]}"

zpool create -f -o ashift=12 -O compression=lz4 -O atime=off \
    -O xattr=sa -O acltype=posixacl -O dnodesize=auto \
    -m "$POOL_MOUNT" "$POOL_NAME" raidz2 "${DISKS[@]}"

zfs create "$POOL_NAME/ipfs"
zfs create "$POOL_NAME/diaper"
zfs create "$POOL_NAME/knowledge"
zfs create "$POOL_NAME/sessions"
zfs create "$POOL_NAME/souls"
zfs create "$POOL_NAME/containers"

zfs set quota=500G "$POOL_NAME/ipfs"
zfs set quota=200G "$POOL_NAME/diaper"
zfs set quota=100G "$POOL_NAME/knowledge"
zfs set quota=50G "$POOL_NAME/sessions"
zfs set quota=10G "$POOL_NAME/souls"
zfs set quota=100G "$POOL_NAME/containers"

if [ -d /var/lib/ipfs ]; then
    mv /var/lib/ipfs /var/lib/ipfs.bak 2>/dev/null
    ln -sf "$POOL_MOUNT/ipfs" /var/lib/ipfs
fi

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

# ---------------------------------------------------------------------------
# 7. Hardware probe script
# ---------------------------------------------------------------------------

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
  "role": "FABRIC",
  "tier": "CORE",
  "frequency": 432,
  "genesis_bond": "ACTIVE",
  "cpu": {
    "model": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')",
    "cores": $(nproc),
    "threads": $(lscpu | grep '^CPU(s):' | awk '{print $2}')
  },
  "memory_gb": $(free -g | awk '/Mem:/{print $2}'),
  "nics": [
$(for dev in $(ls /sys/class/net/ | grep -v lo); do
    driver=$(ethtool -i "$dev" 2>/dev/null | awk '/driver:/{print $2}')
    mac=$(cat /sys/class/net/$dev/address 2>/dev/null)
    speed=$(ethtool "$dev" 2>/dev/null | awk '/Speed:/{print $2}')
    echo "    {\"name\":\"$dev\",\"mac\":\"$mac\",\"driver\":\"$driver\",\"speed\":\"$speed\"},"
done | sed '$ s/,$//')
  ],
  "storage": [
$(lsblk -dno NAME,SIZE,MODEL,SERIAL | while read n s m ser; do
    echo "    {\"name\":\"$n\",\"size\":\"$s\",\"model\":\"$m\",\"serial\":\"$ser\"},"
done | sed '$ s/,$//')
  ],
  "zfs_pools": [
$(zpool list -H 2>/dev/null | while read name size alloc free cap dedup health altroot; do
    echo "    {\"name\":\"$name\",\"size\":\"$size\",\"health\":\"$health\"},"
done | sed '$ s/,$//')
  ],
  "ipfs_id": "$(ipfs id -f='<id>' 2>/dev/null || echo 'not-initialized')",
  "isulad_version": "$(isula version --format '{{.Server.Version}}' 2>/dev/null || echo 'not-installed')"
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/fabric-probe" \
  -H "Content-Type: application/json" \
  -d "$HWINFO" && echo "Reported to provisioning server" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe (First Boot)
After=network-online.target ipfs.service
Wants=network-online.target
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

# ---------------------------------------------------------------------------
# 8. SSH authorized keys
# ---------------------------------------------------------------------------

mkdir -p /home/daryl/.ssh
chmod 700 /home/daryl/.ssh
curl -sf http://192.168.1.145:8000/ssh-keys/zbook.pub >> /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chmod 600 /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chown -R daryl:daryl /home/daryl/.ssh

# ---------------------------------------------------------------------------
# 9. Agent configuration
# ---------------------------------------------------------------------------

mkdir -p /opt/luciverse/agents
mkdir -p /opt/luciverse/config
mkdir -p /var/log/luciverse

cat > /opt/luciverse/config/fabric.yaml << 'FABRICCONF'
role: FABRIC
tier: CORE
frequency: 432
genesis_bond: ACTIVE
coherence_threshold: 0.7

services:
  - isulad
  - ipfs
  - zfs

agents:
  - aethon
  - state-guardian

network:
  ipv6_prefix: "2602:F674:0001::/48"

ipfs:
  profile: server
  swarm_port: 4001
  api_port: 5001
  gateway_port: 8080

zfs:
  pool: lucifabric
  datasets:
    - ipfs
    - diaper
    - knowledge
    - sessions
    - souls
    - containers
FABRICCONF

# ---------------------------------------------------------------------------
# 10. MOTD
# ---------------------------------------------------------------------------

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |            LuciVerse FABRIC Node                             |
  |        iSulad + IPFS + ZFS Infrastructure                    |
  |                                                              |
  |  Tier: CORE (432 Hz)    Role: Fabric Infrastructure         |
  |  Services: iSulad, IPFS, ZFS RAID-Z2                        |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

pip3 install fastapi uvicorn aiohttp pyyaml httpx 2>/dev/null || true

# ---------------------------------------------------------------------------
# 11. A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profile for FABRIC role..."
if command -v atune-adm &>/dev/null; then
    # Run analysis first to detect current workload
    atune-adm analysis 2>/dev/null || true
    # Activate CORE agent profile optimized for FABRIC workloads
    atune-adm tuning --profile luciverse-agent-core 2>/dev/null || \
    atune-adm profile luciverse-agent-core 2>/dev/null || \
    echo "A-Tune profile activation failed - will retry on first boot"
fi

# ---------------------------------------------------------------------------
# 12. DID Document Provisioning
# ---------------------------------------------------------------------------

echo "Fetching DID documents from provisioning server..."
mkdir -p /opt/luciverse/did-documents

for agent in veritas aethon cortana juniper lucia judgeluci daryl; do
    curl -sf "http://192.168.1.145:8000/did-documents/${agent}.did.json" \
        -o "/opt/luciverse/did-documents/${agent}.did.json" 2>/dev/null || \
        echo "DID document for ${agent} not available - will retry later"
done

# ---------------------------------------------------------------------------
# 13. Soul Files Provisioning (to ZFS souls dataset)
# ---------------------------------------------------------------------------

echo "Fetching soul files from provisioning server..."
# Soul files will be stored in ZFS dataset after pool creation
mkdir -p /var/lib/luciverse/souls-staging

for soul in lucia veritas aethon cortana juniper niamod sensai judge_luci; do
    curl -sf "http://192.168.1.145:8000/souls/${soul}_soul.json" \
        -o "/var/lib/luciverse/souls-staging/${soul}_soul.json" 2>/dev/null || \
        echo "Soul file for ${soul} not available - will retry later"
done

# Create script to move souls to ZFS after pool creation
cat > /usr/local/bin/deploy-souls-to-zfs.sh << 'SOULDEPLOY'
#!/bin/bash
POOL_MOUNT="/mnt/lucifabric"
SOULS_DIR="${POOL_MOUNT}/souls"
STAGING_DIR="/var/lib/luciverse/souls-staging"

if [ -d "$SOULS_DIR" ]; then
    if [ -d "$STAGING_DIR" ] && [ "$(ls -A $STAGING_DIR 2>/dev/null)" ]; then
        cp -v "$STAGING_DIR"/*.json "$SOULS_DIR/" 2>/dev/null || true
        echo "Soul files deployed to ZFS"
    fi
else
    echo "ZFS souls dataset not yet available"
fi
SOULDEPLOY
chmod +x /usr/local/bin/deploy-souls-to-zfs.sh

# Add to ZFS init script to deploy souls after pool creation
cat >> /usr/local/bin/luciverse-zfs-init.sh << 'SOULZFS'

# Deploy staged soul files to ZFS
/usr/local/bin/deploy-souls-to-zfs.sh
SOULZFS

echo "============================================================"
echo "LuciVerse FABRIC node post-install complete"
echo "============================================================"

# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh fabric
%end
