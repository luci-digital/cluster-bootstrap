# ============================================================================
# LuciVerse COMPUTE Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R630 servers (128GB RAM, 40 threads)
# Role: StratoVirt VM runtime, general compute
# Tier: COMN (528 Hz)
# Count: 2 nodes (.152-.153)
# ============================================================================

install
text
reboot

lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

network --bootproto=dhcp --device=link --activate --hostname=compute-node.lucidigital.net

rootpw --plaintext TempInstall741!
user --name=daryl --groups=wheel --password=TempInstall741! --plaintext

firewall --enabled --ssh --port=6443:tcp,10250:tcp,2379:tcp,2380:tcp,9520:tcp,9523:tcp,9999:tcp
selinux --permissive
auth --enableshadow --passalgo=sha512

ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
part /boot/efi --fstype=efi --size=600
part /boot --fstype=ext4 --size=1024
part pv.01 --size=1 --grow
volgroup vg_root pv.01
logvol / --vgname=vg_root --name=lv_root --fstype=ext4 --size=50000
logvol /var --vgname=vg_root --name=lv_var --fstype=ext4 --size=80000
logvol /var/lib/libvirt --vgname=vg_root --name=lv_libvirt --fstype=ext4 --size=200000
logvol swap --vgname=vg_root --name=lv_swap --size=16384

bootloader --append="crashkernel=auto hugepagesz=2M hugepages=2048 intel_iommu=on iommu=pt kvm-intel.nested=1"

%packages
@base
@core
@network-tools
@virtualization-host-environment
iSulad
isula-build
crun
StratoVirt
libvirt
libvirt-daemon
libvirt-daemon-driver-qemu
libvirt-client
virt-install
qemu-kvm
qemu-img
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
cockpit-machines
%end

%post --log=/root/luciverse-compute-postinstall.log

echo "============================================================"
echo "LuciVerse COMPUTE Node Post-Install"
echo "Tier: COMN (528 Hz) - StratoVirt/KVM"
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
systemctl enable libvirtd
systemctl enable atuned
systemctl enable atune-engine

# System tuning
cat > /etc/sysctl.d/90-luciverse-compute.conf << 'SYSCTL'
vm.swappiness = 10
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
vm.overcommit_memory = 1
vm.nr_hugepages = 2048
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 65535
net.ipv4.tcp_congestion_control = bbr
fs.file-max = 2097152
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 524288
kernel.sched_autogroup_enabled = 0
SYSCTL

# Kernel modules
cat > /etc/modules-load.d/luciverse-compute.conf << 'MODULES'
kvm
kvm_intel
vfio
vfio_iommu_type1
vfio_pci
bridge
br_netfilter
8021q
vhost_net
tun
ixgbe
i40e
MODULES

# iSulad config
mkdir -p /etc/isulad
cat > /etc/isulad/daemon.json << 'ISULAD'
{
  "group": "isula",
  "default-runtime": "lcr",
  "storage-driver": "overlay2",
  "registry-mirrors": ["https://registry.lucidigital.net"],
  "insecure-registries": ["192.168.1.146:5050"],
  "log-driver": "json-file",
  "log-opts": {"max-size": "100m", "max-file": "3"},
  "pod-sandbox-image": "registry.lucidigital.net/pause:3.9",
  "cni-bin-dir": "/opt/cni/bin",
  "cni-conf-dir": "/etc/cni/net.d"
}
ISULAD

# StratoVirt config
mkdir -p /etc/stratovirt
cat > /etc/stratovirt/stratovirt.json << 'STRATOVIRT'
{
  "machine": {"type": "microvm", "mem_share": true},
  "smp": {"cpus": 4, "max_cpus": 8},
  "memory": {"size": "4G", "mem_path": "/dev/hugepages"},
  "console": {"console_type": "virtio-console"}
}
STRATOVIRT

cat > /etc/systemd/system/stratovirt@.service << 'STRATOSVC'
[Unit]
Description=StratoVirt VM %i
After=network-online.target libvirtd.service

[Service]
Type=simple
ExecStart=/usr/bin/stratovirt -config /var/lib/stratovirt/vms/%i/config.json
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
STRATOSVC

mkdir -p /var/lib/stratovirt/{vms,images}

# K8s worker install script
cat > /usr/local/bin/install-k8s-worker.sh << 'K8SINSTALL'
#!/bin/bash
K8S_VERSION="${K8S_VERSION:-1.29}"
CONTROL_PLANE="${CONTROL_PLANE:-192.168.1.144}"

if systemctl is-active kubelet &>/dev/null; then
    echo "Kubernetes already running"
    exit 0
fi

dnf install -y k8s-install || dnf install -y kubelet kubeadm kubectl
systemctl enable kubelet

echo "Waiting for join token from provisioning server..."
# Note: K8s join token is served by PXE server at 192.168.1.145, not control plane
until curl -sf "http://192.168.1.145:9999/k8s-join-token" -o /tmp/join-token.sh; do
    sleep 30
done

chmod +x /tmp/join-token.sh
/tmp/join-token.sh
K8SINSTALL
chmod +x /usr/local/bin/install-k8s-worker.sh

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
  "role": "COMPUTE",
  "tier": "COMN",
  "frequency": 528,
  "genesis_bond": "ACTIVE",
  "cpu": {
    "model": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')",
    "cores": $(nproc),
    "kvm_enabled": $(grep -q vmx /proc/cpuinfo && echo 'true' || echo 'false')
  },
  "memory_gb": $(free -g | awk '/Mem:/{print $2}'),
  "virtualization": {
    "kvm_loaded": $(lsmod | grep -q kvm && echo 'true' || echo 'false'),
    "libvirt_active": $(systemctl is-active libvirtd &>/dev/null && echo 'true' || echo 'false'),
    "stratovirt_installed": $(command -v stratovirt &>/dev/null && echo 'true' || echo 'false')
  },
  "kubernetes": {
    "kubelet_active": $(systemctl is-active kubelet &>/dev/null && echo 'true' || echo 'false')
  }
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/compute-probe" \
  -H "Content-Type: application/json" -d "$HWINFO" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe
After=network-online.target libvirtd.service
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

cat > /opt/luciverse/config/compute.yaml << 'COMPUTECONF'
role: COMPUTE
tier: COMN
frequency: 528
genesis_bond: ACTIVE
coherence_threshold: 0.7
services: [isulad, libvirtd, stratovirt, kubelet]
agents: [diaphragm, flow-conductor]
virtualization:
  default_hypervisor: stratovirt
  fallback: qemu-kvm
  hugepages: 2048
kubernetes:
  role: worker
  control_plane: "192.168.1.144"
  cni: cilium
network:
  ipv6_prefix: "2602:F674:0100::/48"
COMPUTECONF

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |            LuciVerse COMPUTE Node                            |
  |        StratoVirt VMs, Kubernetes Worker                     |
  |                                                              |
  |  Tier: COMN (528 Hz)    Role: Virtualization                |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

pip3 install fastapi uvicorn aiohttp pyyaml httpx 2>/dev/null || true

# ---------------------------------------------------------------------------
# A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profile for COMPUTE role..."
if command -v atune-adm &>/dev/null; then
    atune-adm analysis 2>/dev/null || true
    # Activate COMN agent profile for compute workloads
    atune-adm tuning --profile luciverse-agent-comn 2>/dev/null || \
    atune-adm profile luciverse-agent-comn 2>/dev/null || \
    echo "A-Tune profile activation failed"
fi

echo "COMPUTE post-install complete"

# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh compute
%end
