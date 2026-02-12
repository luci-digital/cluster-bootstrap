# ============================================================================
# LuciVerse CORE-GPU Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R730 server with GPU (384GB RAM, 56 threads)
# Role: Core GPU processing, Sensai ML agent
# Tier: CORE (432 Hz)
# Count: 1 node (.143)
# ============================================================================

install
text
reboot

lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

network --bootproto=dhcp --device=link --activate --hostname=core-gpu.lucidigital.net

rootpw --plaintext TempInstall741!
user --name=daryl --groups=wheel --password=TempInstall741! --plaintext

firewall --enabled --ssh --port=8080:tcp,11434:tcp,9432:tcp,9433:tcp,9434:tcp,9999:tcp
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
logvol /var/lib/models --vgname=vg_root --name=lv_models --fstype=ext4 --size=300000
logvol swap --vgname=vg_root --name=lv_swap --size=32768

bootloader --append="crashkernel=auto hugepagesz=1G hugepages=64 intel_iommu=on iommu=pt rd.driver.blacklist=nouveau nouveau.modeset=0"

%packages
@base
@core
@network-tools
iSulad
isula-build
crun
atune
atune-engine
kernel-devel
kernel-headers
gcc
gcc-c++
make
dkms
elfutils-libelf-devel
python3
python3-pip
python3-devel
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
%end

%post --log=/root/luciverse-core-gpu-postinstall.log

echo "============================================================"
echo "LuciVerse CORE-GPU Node Post-Install"
echo "Tier: CORE (432 Hz) - ML Processing"
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
systemctl enable atuned
systemctl enable atune-engine

# Blacklist nouveau
cat > /etc/modprobe.d/blacklist-nouveau.conf << 'BLACKLIST'
blacklist nouveau
blacklist lbm-nouveau
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
BLACKLIST
dracut --force

# System tuning
cat > /etc/sysctl.d/90-luciverse-core-gpu.conf << 'SYSCTL'
vm.swappiness = 1
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
vm.overcommit_memory = 1
vm.nr_hugepages = 64
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 65535
net.ipv4.tcp_congestion_control = bbr
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
fs.file-max = 2097152
SYSCTL

# Kernel modules
cat > /etc/modules-load.d/luciverse-core-gpu.conf << 'MODULES'
vfio
vfio_iommu_type1
vfio_pci
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
  "runtimes": {
    "nvidia": {
      "path": "/usr/bin/nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "log-driver": "json-file",
  "log-opts": {"max-size": "100m", "max-file": "3"}
}
ISULAD

# NVIDIA driver install
cat > /usr/local/bin/install-nvidia-driver.sh << 'NVIDIAINSTALL'
#!/bin/bash
NVIDIA_DRIVER_VERSION="${NVIDIA_DRIVER_VERSION:-550.54.14}"

if ! lspci | grep -i nvidia; then
    echo "No NVIDIA GPU detected"
    exit 0
fi

if nvidia-smi &>/dev/null; then
    echo "NVIDIA driver already installed"
    nvidia-smi
    exit 0
fi

cat > /etc/yum.repos.d/nvidia-cuda.repo << 'REPO'
[nvidia-cuda]
name=NVIDIA CUDA Repository
baseurl=https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/
enabled=1
gpgcheck=1
gpgkey=https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/D42D0685.pub
REPO

dnf install -y nvidia-driver nvidia-driver-cuda cuda-toolkit-12-4 nvidia-container-toolkit || {
    DRIVER_URL="https://us.download.nvidia.com/tesla/${NVIDIA_DRIVER_VERSION}/NVIDIA-Linux-x86_64-${NVIDIA_DRIVER_VERSION}.run"
    curl -L -o /tmp/nvidia-driver.run "$DRIVER_URL"
    chmod +x /tmp/nvidia-driver.run
    /tmp/nvidia-driver.run --silent --dkms
}

nvidia-ctk runtime configure --runtime=docker 2>/dev/null || true
nvidia-smi
NVIDIAINSTALL
chmod +x /usr/local/bin/install-nvidia-driver.sh

cat > /etc/systemd/system/nvidia-driver-install.service << 'NVIDIASVC'
[Unit]
Description=NVIDIA Driver Installation
After=network-online.target
ConditionPathExists=!/var/lib/luciverse/.nvidia-installed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/install-nvidia-driver.sh
ExecStartPost=/bin/mkdir -p /var/lib/luciverse
ExecStartPost=/bin/touch /var/lib/luciverse/.nvidia-installed
TimeoutStartSec=1800
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
NVIDIASVC
systemctl enable nvidia-driver-install.service

# Ollama install
cat > /usr/local/bin/install-ollama.sh << 'OLLAMAINSTALL'
#!/bin/bash
if command -v ollama &>/dev/null; then exit 0; fi

curl -fsSL https://ollama.com/install.sh | sh

cat > /etc/systemd/system/ollama.service << 'OLLAMA'
[Unit]
Description=Ollama LLM Server (CORE-GPU)
After=network-online.target nvidia-driver-install.service

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama serve
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_MODELS=/var/lib/models/ollama"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
OLLAMA

mkdir -p /var/lib/models/ollama
systemctl daemon-reload
systemctl enable ollama.service
OLLAMAINSTALL
chmod +x /usr/local/bin/install-ollama.sh

cat > /etc/systemd/system/ollama-install.service << 'OLLAMASVC'
[Unit]
Description=Ollama Installation
After=nvidia-driver-install.service
ConditionPathExists=!/var/lib/luciverse/.ollama-installed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/install-ollama.sh
ExecStartPost=/bin/touch /var/lib/luciverse/.ollama-installed
TimeoutStartSec=600
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
OLLAMASVC
systemctl enable ollama-install.service

# Mount model storage
mkdir -p /var/lib/models
mkdir -p /mnt/storage-models

cat > /usr/local/bin/mount-model-storage.sh << 'MOUNTSTORAGE'
#!/bin/bash
STORAGE_NODES=("192.168.1.146" "192.168.1.147")

for node in "${STORAGE_NODES[@]}"; do
    if ping -c 1 -W 2 "$node" &>/dev/null; then
        mount -t nfs "${node}:/mnt/lucistorage/models" /mnt/storage-models && {
            ln -sf /mnt/storage-models /var/lib/models/shared
            exit 0
        }
    fi
done
echo "No storage nodes available"
MOUNTSTORAGE
chmod +x /usr/local/bin/mount-model-storage.sh

cat > /etc/systemd/system/mount-model-storage.service << 'MOUNTSVC'
[Unit]
Description=Mount Model Storage
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mount-model-storage.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
MOUNTSVC
systemctl enable mount-model-storage.service

# Hardware probe
cat > /usr/local/bin/luciverse-probe.sh << 'PROBE'
#!/bin/bash
PROVISION_SERVER="${PROVISION_SERVER:-192.168.1.145}"
CALLBACK_PORT="${CALLBACK_PORT:-9999}"

PRIMARY_MAC=$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}' | head -1)/address 2>/dev/null || echo "unknown")
SERVICE_TAG=$(dmidecode -s system-serial-number 2>/dev/null || echo "unknown")

GPU_INFO="null"
if command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | \
        awk -F',' '{printf "{\"name\":\"%s\",\"memory\":\"%s\",\"driver\":\"%s\"}", $1, $2, $3}')
fi

HWINFO=$(cat << HWEOF
{
  "hostname": "$(hostname)",
  "primary_mac": "$PRIMARY_MAC",
  "service_tag": "$SERVICE_TAG",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "role": "CORE-GPU",
  "tier": "CORE",
  "frequency": 432,
  "genesis_bond": "ACTIVE",
  "cpu": {"model": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')", "cores": $(nproc)},
  "memory_gb": $(free -g | awk '/Mem:/{print $2}'),
  "gpu": $GPU_INFO,
  "cuda_version": "$(nvcc --version 2>/dev/null | grep release | awk '{print $6}' | tr -d ',' || echo 'not-installed')",
  "services": {
    "ollama": $(systemctl is-active ollama &>/dev/null && echo 'true' || echo 'false')
  }
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/core-gpu-probe" \
  -H "Content-Type: application/json" -d "$HWINFO" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe
After=network-online.target nvidia-driver-install.service ollama-install.service
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
mkdir -p /var/lib/models

cat > /opt/luciverse/config/core-gpu.yaml << 'COREGPUCONF'
role: CORE-GPU
tier: CORE
frequency: 432
genesis_bond: ACTIVE
coherence_threshold: 0.7
services: [isulad, ollama, nvidia-driver]
agents: [sensai, schema-architect]
inference:
  primary: ollama
  models_path: /var/lib/models
network:
  ipv6_prefix: "2602:F674:0001::/48"
COREGPUCONF

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |           LuciVerse CORE-GPU Node                            |
  |      Core GPU Processing, Sensai ML Agent                    |
  |                                                              |
  |  Tier: CORE (432 Hz)    Role: ML Processing                 |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

pip3 install torch transformers accelerate 2>/dev/null || true
pip3 install fastapi uvicorn aiohttp pyyaml httpx 2>/dev/null || true

# ---------------------------------------------------------------------------
# A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profile for CORE-GPU role..."
if command -v atune-adm &>/dev/null; then
    atune-adm analysis 2>/dev/null || true
    # Activate ML inference profile for CORE GPU workloads
    atune-adm tuning --profile luciverse-ml-inference 2>/dev/null || \
    atune-adm profile luciverse-ml-inference 2>/dev/null || \
    echo "A-Tune profile activation failed"
fi

echo "CORE-GPU post-install complete"

# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh core-gpu
%end
