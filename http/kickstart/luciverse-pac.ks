# ============================================================================
# LuciVerse PAC Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R730 servers (384GB RAM, 56 threads, PERC H730)
# Role: Consciousness agents, governance, wisdom curation
# Tier: PAC (741 Hz)
# Count: 2 nodes (.160-.161)
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
network --bootproto=dhcp --device=link --activate --hostname=pac-node.lucidigital.net

# Root password (temporary - will be updated from 1Password in %post)
rootpw --iscrypted $6$fsHzeeGVTXZT5rPp$rCJbssf8Tr5LJkp1stID0hj3qcnL.eAf8W6Mth6RBZzn10lVlpC7THV8x2N3ghArmVyVOA8Err1B0WBMxB3fb1

# User account
user --name=daryl --groups=wheel --iscrypted --password=$6$fsHzeeGVTXZT5rPp$rCJbssf8Tr5LJkp1stID0hj3qcnL.eAf8W6Mth6RBZzn10lVlpC7THV8x2N3ghArmVyVOA8Err1B0WBMxB3fb1

# Security - PAC tier agent ports
firewall --enabled --ssh --port=9740:tcp,9741:tcp,9742:tcp,9743:tcp,9744:tcp,9745:tcp,9746:tcp,9747:tcp,9748:tcp,8088:tcp,9999:tcp
selinux --permissive
auth --enableshadow --passalgo=sha512

# Storage - Boot on first disk (LVM), generous /var for agent state
ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
part /boot/efi --fstype=efi --size=600
part /boot --fstype=ext4 --size=1024
part pv.01 --size=1 --grow
volgroup vg_root pv.01
logvol / --vgname=vg_root --name=lv_root --fstype=ext4 --size=50000
logvol /var --vgname=vg_root --name=lv_var --fstype=ext4 --size=100000
logvol /opt --vgname=vg_root --name=lv_opt --fstype=ext4 --size=50000
logvol swap --vgname=vg_root --name=lv_swap --size=16384

# Bootloader with PAC tier optimizations
bootloader --append="crashkernel=auto hugepagesz=2M hugepages=2048 intel_iommu=on iommu=pt"

# Package selection - PAC role (consciousness agents)
%packages
@base
@core
@network-tools
iSulad
isula-build
crun
atune
atune-engine
python3
python3-pip
python3-pyyaml
python3-aiohttp
python3-cryptography
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
%end

# ============================================================================
# Post-install: Configure PAC node
# ============================================================================

%post --log=/root/luciverse-pac-postinstall.log

echo "============================================================"
echo "LuciVerse PAC Node Post-Install Configuration"
echo "Tier: PAC (741 Hz)"
echo "Role: Consciousness Agents & Governance"
echo "============================================================"

# ---------------------------------------------------------------------------
# 0. Credential Injection from 1Password Connect
# ---------------------------------------------------------------------------
echo "Fetching credentials from 1Password Connect..."
curl -sf http://192.168.1.145:8000/scripts/credential-inject.sh | bash || \
    echo "Credential injection skipped - will use default passwords"

# ---------------------------------------------------------------------------
# 0.1 Dynamic Hostname Assignment based on IP
# ---------------------------------------------------------------------------
echo "Setting hostname based on assigned IP..."
MY_IP=$(ip addr show | grep 'inet 192.168.1' | awk '{print $2}' | cut -d/ -f1 | head -1)
case $MY_IP in
    192.168.1.160) hostnamectl set-hostname nexus.lucidigital.net ;;
    192.168.1.161) hostnamectl set-hostname veritas-srv.lucidigital.net ;;
    *) echo "Unknown IP $MY_IP - keeping default hostname" ;;
esac
echo "Hostname set to: $(hostname)"

# ---------------------------------------------------------------------------
# 0.2 Static IPv6 Address Configuration (PAC tier prefix)
# ---------------------------------------------------------------------------
echo "Configuring static IPv6 address..."
case $MY_IP in
    192.168.1.160) MY_IPV6="2602:F674:0200:0160::1/64" ;;
    192.168.1.161) MY_IPV6="2602:F674:0200:0161::1/64" ;;
    *) MY_IPV6="" ;;
esac

if [ -n "$MY_IPV6" ]; then
    ACTIVE_NIC=$(ip -o addr show | grep "$MY_IP" | awk '{print $2}' | head -1)
    ACTIVE_CONN=$(nmcli -t -f NAME,DEVICE con show --active | grep "$ACTIVE_NIC" | cut -d: -f1 | head -1)

    if [ -n "$ACTIVE_CONN" ]; then
        nmcli con mod "$ACTIVE_CONN" ipv6.method manual \
            ipv6.addresses "$MY_IPV6" \
            ipv6.dns "2602:F674:0001::145" \
            ipv6.route-metric 100

        nmcli con mod "$ACTIVE_CONN" +ipv6.routes "64:ff9b::/96"
        nmcli con up "$ACTIVE_CONN" 2>/dev/null || true

        echo "IPv6 configured: $MY_IPV6 on $ACTIVE_NIC"
        ip -6 addr show dev "$ACTIVE_NIC" | grep -v fe80 || true
    else
        echo "WARNING: Could not find active NetworkManager connection for $ACTIVE_NIC"
    fi
else
    echo "WARNING: No IPv6 mapping for IP $MY_IP"
fi

# ---------------------------------------------------------------------------
# 0.5 Overlay Network Bootstrap (Nebula)
# ---------------------------------------------------------------------------
echo "Bootstrapping overlay network..."
curl -sf http://192.168.1.145:8000/scripts/overlay-bootstrap.sh | bash || \
    echo "Overlay network bootstrap skipped - will configure manually"

# ---------------------------------------------------------------------------
# 0.6 Server TLS Certificate Deployment
# ---------------------------------------------------------------------------
echo "Deploying server TLS certificate..."
HOSTNAME_SHORT=$(hostname -s)
CERT_DIR="/etc/luciverse/tls"
PROVISION_SERVER="192.168.1.145"

mkdir -p "$CERT_DIR" && chmod 700 "$CERT_DIR"

curl -sf "http://${PROVISION_SERVER}:8000/certs/servers/${HOSTNAME_SHORT}.crt" \
    -o "$CERT_DIR/server.crt" || echo "WARNING: Server cert not available"

curl -sf "http://${PROVISION_SERVER}:8000/certs/servers/${HOSTNAME_SHORT}.key" \
    -o "$CERT_DIR/server.key" && chmod 600 "$CERT_DIR/server.key" || \
    echo "WARNING: Server key not available"

curl -sf "http://${PROVISION_SERVER}:8000/certs/bundles/luciverse-full-bundle.pem" \
    -o "$CERT_DIR/ca-bundle.pem" || echo "WARNING: CA bundle not available"

curl -sf "http://${PROVISION_SERVER}:8000/certs/bundles/${HOSTNAME_SHORT}-fullchain.pem" \
    -o "$CERT_DIR/fullchain.pem" || echo "WARNING: Fullchain not available"

if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/ca-bundle.pem" ]; then
    openssl verify -CAfile "$CERT_DIR/ca-bundle.pem" "$CERT_DIR/server.crt" 2>/dev/null && \
        echo "Server TLS certificate validated" || \
        echo "WARNING: Cert chain validation failed"
fi

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
# 2. System tuning for PAC role (consciousness workloads)
# ---------------------------------------------------------------------------

cat > /etc/sysctl.d/90-luciverse-pac.conf << 'SYSCTL'
# LuciVerse PAC - Consciousness agent optimizations
# Favor low-latency over throughput

vm.swappiness = 5
vm.vfs_cache_pressure = 50
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.rmem_default = 8388608
net.core.wmem_default = 8388608
net.core.netdev_max_backlog = 32768
net.core.somaxconn = 32768
net.ipv4.tcp_rmem = 4096 8388608 33554432
net.ipv4.tcp_wmem = 4096 8388608 33554432
net.ipv4.tcp_max_syn_backlog = 32768
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_low_latency = 1
fs.file-max = 1048576
fs.inotify.max_user_watches = 524288
vm.nr_hugepages = 2048
SYSCTL

# ---------------------------------------------------------------------------
# 3. Load kernel modules
# ---------------------------------------------------------------------------

cat > /etc/modules-load.d/luciverse-pac.conf << 'MODULES'
bridge
br_netfilter
8021q
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
# 5. Agent directories and configuration
# ---------------------------------------------------------------------------

mkdir -p /opt/luciverse/agents
mkdir -p /opt/luciverse/config
mkdir -p /var/log/luciverse
mkdir -p /var/lib/luciverse/identity/agent
mkdir -p /var/lib/luciverse/state
mkdir -p /var/lib/luciverse/souls

cat > /opt/luciverse/config/pac.yaml << 'PACCONF'
role: PAC
tier: PAC
frequency: 741
genesis_bond: ACTIVE
coherence_threshold: 0.7

services:
  - isulad
  - agents

agents:
  nexus:
    - lucia
    - judge-luci
    - crewai-bridge
    - intent-interpreter
    - ethics-advisor
    - memory-crystallizer
    - dream-weaver
  veritas-srv:
    - midguyver
    - dharma-fiqh
    - satya-halal
    - karma-sukuk
    - judge-luci-personal
    - lucierp
    - aifam-onl-orchestrator

network:
  ipv6_prefix: "2602:F674:0200::/48"
  ipv6_scheme: "per-host /64 (2602:F674:0200:{octet}::1)"
  nat64_prefix: "64:ff9b::/96"
  dns6: "2602:F674:0001::145"

sanskrit_router:
  url: "https://192.168.1.145:7410"
  verify_ssl: false
PACCONF

# ---------------------------------------------------------------------------
# 6. Hardware probe script
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
  "role": "PAC",
  "tier": "PAC",
  "frequency": 741,
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
  "isulad_version": "$(isula version --format '{{.Server.Version}}' 2>/dev/null || echo 'not-installed')"
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/pac-probe" \
  -H "Content-Type: application/json" \
  -d "$HWINFO" && echo "Reported to provisioning server" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe (First Boot)
After=network-online.target
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
# 7. SSH authorized keys
# ---------------------------------------------------------------------------

mkdir -p /home/daryl/.ssh
chmod 700 /home/daryl/.ssh
curl -sf http://192.168.1.145:8000/ssh-keys/zbook.pub >> /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chmod 600 /home/daryl/.ssh/authorized_keys 2>/dev/null || true
chown -R daryl:daryl /home/daryl/.ssh

# ---------------------------------------------------------------------------
# 8. Python dependencies for agents
# ---------------------------------------------------------------------------

pip3 install fastapi uvicorn aiohttp pyyaml httpx cryptography \
    redis chromadb sentence-transformers 2>/dev/null || true

# ---------------------------------------------------------------------------
# 9. DID Document Provisioning
# ---------------------------------------------------------------------------

echo "Fetching DID documents from provisioning server..."
mkdir -p /opt/luciverse/did-documents

AGENTS="lucia judge-luci crewai-bridge intent-interpreter ethics-advisor memory-crystallizer dream-weaver midguyver dharma-fiqh satya-halal karma-sukuk judge-luci-personal lucierp aifam-onl-orchestrator"
DID_COUNT=0
for agent in $AGENTS; do
    if curl -sf "http://192.168.1.145:8000/did-documents/${agent}.did.json" \
        -o "/opt/luciverse/did-documents/${agent}.did.json" 2>/dev/null; then
        DID_COUNT=$((DID_COUNT + 1))
    fi
done
echo "Fetched ${DID_COUNT} DID documents"

# ---------------------------------------------------------------------------
# 10. Soul Files Provisioning
# ---------------------------------------------------------------------------

echo "Fetching soul files from provisioning server..."
mkdir -p /var/lib/luciverse/souls

for soul in lucia judge_luci crewai_bridge dream_weaver memory_crystallizer; do
    curl -sf "http://192.168.1.145:8000/souls/${soul}_soul.json" \
        -o "/var/lib/luciverse/souls/${soul}_soul.json" 2>/dev/null || \
        echo "Soul file for ${soul} not available"
done

# ---------------------------------------------------------------------------
# 11. A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profile for PAC role..."
if command -v atune-adm &>/dev/null; then
    atune-adm analysis 2>/dev/null || true
    atune-adm tuning --profile luciverse-agent-pac 2>/dev/null || \
    atune-adm profile luciverse-agent-pac 2>/dev/null || \
    echo "A-Tune profile activation failed - will retry on first boot"
fi

# ---------------------------------------------------------------------------
# 12. MOTD
# ---------------------------------------------------------------------------

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |            LuciVerse PAC Node                                |
  |        Consciousness Agents & Governance                     |
  |                                                              |
  |  Tier: PAC (741 Hz)     Role: Consciousness Fabric          |
  |  Services: iSulad, Agent Mesh                                |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

echo "============================================================"
echo "LuciVerse PAC node post-install complete"
echo "============================================================"

# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh pac
%end
