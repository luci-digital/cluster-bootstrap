# ============================================================================
# LuciSwitch Z97 - openEuler 25.09 Kickstart
# ============================================================================
# Target: MSI Z97 tower (32GB DDR3, 3x PCIe, Haswell)
# Role: Software RDMA switch + PXE server + provisioning API
# IP: 192.168.1.179 (luciswitch.lucidigital.net)
# Agent: luciswitch @ CORE 432 Hz, port 9540/9541
# ============================================================================

# Install mode
install
text
reboot

# Language and keyboard
lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

# Network - use first available NIC for install, full config in %post
network --bootproto=dhcp --device=link --activate --hostname=luciswitch.lucidigital.net

# Root password (change after first boot)
rootpw --plaintext Newdaryl24!

# User
user --name=daryl --groups=wheel --password=Newdaryl24! --plaintext

# Security
firewall --enabled --ssh --port=9540:tcp,9541:tcp,9999:tcp,8000:tcp,69:udp,67:udp,68:udp
selinux --permissive
auth --enableshadow --passalgo=sha512

# Storage - use first disk, minimal layout for a network appliance
ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
autopart --type=lvm --fstype=ext4

# Bootloader
bootloader --append="crashkernel=auto hugepagesz=2M hugepages=512 intel_iommu=on iommu=pt"

# Package selection - minimal + networking tools
%packages
@base
@core
@network-tools
python3
python3-pip
python3-pyyaml
python3-aiohttp
dnsmasq
bridge-utils
iproute
tcpdump
ethtool
lldpad
iperf3
numactl
pciutils
usbutils
lm_sensors
dmidecode
nmap
tmux
vim
git
rsync
openssh-server
openssh-clients
cockpit
cockpit-bridge
cockpit-ws
cockpit-system
cockpit-networkmanager
rdma-core
libibverbs
libibverbs-utils
librdmacm
librdmacm-utils
infiniband-diags
perftest
%end

# ============================================================================
# Post-install: Configure LuciSwitch
# ============================================================================

%post --log=/root/luciswitch-postinstall.log

echo "============================================================"
echo "LuciSwitch Z97 Post-Install Configuration"
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. Enable essential services
# ---------------------------------------------------------------------------

systemctl enable sshd
systemctl enable cockpit.socket
systemctl enable dnsmasq
systemctl enable lldpad

# ---------------------------------------------------------------------------
# 2. System tuning for packet forwarding
# ---------------------------------------------------------------------------

cat > /etc/sysctl.d/90-luciswitch.conf << 'SYSCTL'
# LuciSwitch - Network forwarding and bridge optimization

# Enable IPv4/IPv6 forwarding
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1

# Bridge performance
net.bridge.bridge-nf-call-iptables = 0
net.bridge.bridge-nf-call-ip6tables = 0
net.bridge.bridge-nf-call-arptables = 0

# Increase network buffers
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 65535

# TCP tuning
net.ipv4.tcp_rmem = 4096 1048576 16777216
net.ipv4.tcp_wmem = 4096 1048576 16777216
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_ecn = 1

# ARP tuning for bridge
net.ipv4.neigh.default.gc_thresh1 = 4096
net.ipv4.neigh.default.gc_thresh2 = 8192
net.ipv4.neigh.default.gc_thresh3 = 16384

# Disable ICMP redirects (we are a router)
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# RDMA hugepages
vm.nr_hugepages = 512
SYSCTL

# ---------------------------------------------------------------------------
# 3. Load RDMA kernel modules on boot
# ---------------------------------------------------------------------------

cat > /etc/modules-load.d/rdma.conf << 'MODULES'
# RDMA/RoCE kernel modules for LuciSwitch
ib_core
ib_uverbs
rdma_cm
rdma_ucm
# Broadcom RoCE (loaded when NIC detected)
bnxt_en
bnxt_re
# Intel fallback
ixgbe
i40e
# Bridge
bridge
br_netfilter
8021q
MODULES

# ---------------------------------------------------------------------------
# 4. DCB/PFC configuration script (runs after NICs are up)
# ---------------------------------------------------------------------------

cat > /usr/local/bin/luciswitch-dcb-setup.sh << 'DCB'
#!/bin/bash
# Configure DCB/PFC on all RDMA-capable NICs for lossless RoCEv2
# Runs as a systemd service after network is up

for dev in $(ls /sys/class/net/ | grep -v lo); do
    # Check if device supports DCB
    if ethtool -i "$dev" 2>/dev/null | grep -q "bnxt_en\|mlx5\|i40e\|ixgbe"; then
        echo "Configuring DCB/PFC on $dev"

        # Set MTU 9000 (jumbo frames for RDMA)
        ip link set "$dev" mtu 9000 2>/dev/null

        # Enable PFC on priority 3 (lossless RoCE)
        if command -v dcb >/dev/null 2>&1; then
            dcb pfc set dev "$dev" prio-pfc 0:off 1:off 2:off 3:on 4:off 5:off 6:off 7:off 2>/dev/null
        elif command -v mlnx_qos >/dev/null 2>&1; then
            mlnx_qos -i "$dev" --pfc 0,0,0,1,0,0,0,0 2>/dev/null
        fi

        # Enable ECN
        if command -v dcb >/dev/null 2>&1; then
            dcb ets set dev "$dev" tc-tsa 0:ets 1:ets 2:ets 3:strict 2>/dev/null
        fi

        echo "  $dev: PFC priority 3, MTU 9000, ECN enabled"
    fi
done
DCB
chmod +x /usr/local/bin/luciswitch-dcb-setup.sh

# Systemd service for DCB setup
cat > /etc/systemd/system/luciswitch-dcb.service << 'DCBSVC'
[Unit]
Description=LuciSwitch DCB/PFC Configuration
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/luciswitch-dcb-setup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
DCBSVC
systemctl enable luciswitch-dcb.service

# ---------------------------------------------------------------------------
# 5. Hardware probe script (reports back to ZBook on first boot)
# ---------------------------------------------------------------------------

cat > /usr/local/bin/luciswitch-probe.sh << 'PROBE'
#!/bin/bash
# Probe hardware and report to ZBook provisioning server
# Try main LAN first (post-reboot), fallback to OOB
ZBOOK="http://192.168.1.146:9999"
ZBOOK_OOB="http://10.0.0.1:9999"

HWINFO=$(cat << HWEOF
{
  "hostname": "$(hostname)",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cpu": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')",
  "cores": $(nproc),
  "ram_gb": $(free -g | awk '/Mem:/{print $2}'),
  "nics": [
    $(for dev in $(ls /sys/class/net/ | grep -v lo); do
      driver=$(ethtool -i "$dev" 2>/dev/null | awk '/driver:/{print $2}')
      mac=$(cat /sys/class/net/$dev/address 2>/dev/null)
      speed=$(ethtool "$dev" 2>/dev/null | awk '/Speed:/{print $2}')
      echo "    {\"name\":\"$dev\",\"mac\":\"$mac\",\"driver\":\"$driver\",\"speed\":\"$speed\"},"
    done | sed '$ s/,$//')
  ],
  "pcie": [
    $(lspci -nn | grep -iE 'ethernet|network|broadcom|intel.*gig|mellanox' | while read line; do
      echo "    \"$line\","
    done | sed '$ s/,$//')
  ],
  "rdma_devices": [
    $(ibv_devices 2>/dev/null | tail -n +2 | while read dev; do
      echo "    \"$dev\","
    done | sed '$ s/,$//')
  ],
  "storage": [
    $(lsblk -dno NAME,SIZE,MODEL | while read n s m; do
      echo "    {\"name\":\"$n\",\"size\":\"$s\",\"model\":\"$m\"},"
    done | sed '$ s/,$//')
  ],
  "genesis_bond": "ACTIVE",
  "role": "luciswitch",
  "tier": "CORE",
  "frequency": 432
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

# Report to ZBook
# Try main LAN, then OOB network
curl -sf -X POST "$ZBOOK/callback/luciswitch-probe" \
  -H "Content-Type: application/json" \
  -d "$HWINFO" && echo "Reported to ZBook (LAN)" || \
curl -sf -X POST "$ZBOOK_OOB/callback/luciswitch-probe" \
  -H "Content-Type: application/json" \
  -d "$HWINFO" && echo "Reported to ZBook (OOB)" || echo "ZBook unreachable (will retry)"
PROBE
chmod +x /usr/local/bin/luciswitch-probe.sh

# Run probe on first boot
cat > /etc/systemd/system/luciswitch-probe.service << 'PROBESVC'
[Unit]
Description=LuciSwitch Hardware Probe (First Boot)
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/var/lib/luciswitch/.probed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/luciswitch-probe.sh
ExecStartPost=/bin/mkdir -p /var/lib/luciswitch
ExecStartPost=/bin/touch /var/lib/luciswitch/.probed

[Install]
WantedBy=multi-user.target
PROBESVC
systemctl enable luciswitch-probe.service

# ---------------------------------------------------------------------------
# 6. SSH authorized keys for ZBook access
# ---------------------------------------------------------------------------

mkdir -p /home/daryl/.ssh
chmod 700 /home/daryl/.ssh

# Copy ZBook's public key (will be populated by provisioning server)
# Try OOB network first (install time), then main LAN
curl -sf http://10.0.0.1:8000/ssh-keys/zbook.pub >> /home/daryl/.ssh/authorized_keys 2>/dev/null || \
curl -sf http://192.168.1.146:8000/ssh-keys/zbook.pub >> /home/daryl/.ssh/authorized_keys 2>/dev/null
chmod 600 /home/daryl/.ssh/authorized_keys 2>/dev/null
chown -R daryl:daryl /home/daryl/.ssh

# ---------------------------------------------------------------------------
# 7. Placeholder for luciswitch-agent (deployed from ZBook after probe)
# ---------------------------------------------------------------------------

mkdir -p /opt/luciverse/agents
cat > /opt/luciverse/agents/README << 'AGENTREADME'
LuciSwitch Agent Deployment
============================
After first boot, the ZBook will:
1. Receive hardware probe via /callback/luciswitch-probe
2. SSH in and deploy luciswitch-agent.py
3. Configure bridge interfaces based on detected NICs
4. Start the agent on port 9540 (TCP) / 9541 (HTTP)

Manual deployment:
  scp daryl@192.168.1.146:~/.claude/skills/agent-mesh/deployment/zimacube-gpu/../luciswitch/luciswitch-agent.py /opt/luciverse/agents/
AGENTREADME

# ---------------------------------------------------------------------------
# 8. Pip install Python dependencies for agent
# ---------------------------------------------------------------------------

pip3 install fastapi uvicorn aiohttp pyyaml 2>/dev/null || true

# ---------------------------------------------------------------------------
# 9. MOTD
# ---------------------------------------------------------------------------

cat > /etc/motd << 'MOTD'

  ╔══════════════════════════════════════════════════════════╗
  ║                 LuciSwitch Z97                          ║
  ║         Software RDMA Switch + PXE Server               ║
  ║                                                         ║
  ║  Tier: CORE (432 Hz)    Agent: :9540/:9541              ║
  ║  Role: Bridge + DCB/PFC + Provisioning                  ║
  ║  Bond: ACTIVE           Coherence: >= 0.7               ║
  ╚══════════════════════════════════════════════════════════╝

MOTD

echo "============================================================"
echo "LuciSwitch Z97 post-install complete"
echo "System will reboot and probe hardware on first boot"
echo "============================================================"

%end
