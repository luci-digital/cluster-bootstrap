# ============================================================================
# LuciVerse INFRA Node - openEuler 25.09 Kickstart
# ============================================================================
# Target: Dell R630 server (128GB RAM, 40 threads)
# Role: FoundationDB, Consul, Nomad orchestration, Step-CA
# Tier: CORE (432 Hz)
# Count: 1 node (.144)
# ============================================================================

install
text
reboot

lang en_US.UTF-8
keyboard us
timezone America/Edmonton --utc

network --bootproto=dhcp --device=link --activate --hostname=infra.lucidigital.net

rootpw --plaintext TempInstall741!
user --name=daryl --groups=wheel --password=TempInstall741! --plaintext

firewall --enabled --ssh --port=4500:tcp,4501:tcp,8300:tcp,8301:tcp,8302:tcp,8500:tcp,8501:tcp,4646:tcp,4647:tcp,4648:tcp,6379:tcp,8443:tcp,9430:tcp,9435:tcp,9999:tcp
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
logvol /var --vgname=vg_root --name=lv_var --fstype=ext4 --size=50000
logvol /var/lib/foundationdb --vgname=vg_root --name=lv_fdb --fstype=ext4 --size=100000
logvol /var/lib/consul --vgname=vg_root --name=lv_consul --fstype=ext4 --size=20000
logvol /var/lib/nomad --vgname=vg_root --name=lv_nomad --fstype=ext4 --size=20000
logvol swap --vgname=vg_root --name=lv_swap --size=16384

bootloader --append="crashkernel=auto hugepagesz=2M hugepages=1024 intel_iommu=on transparent_hugepage=never elevator=none"

%packages
@base
@core
@network-tools
iSulad
isula-build
crun
atune
atune-engine
gcc
gcc-c++
cmake
make
python3
python3-pip
python3-pyyaml
python3-aiohttp
python3-jupyter-core
python3-numpy
python3-pandas
python3-scipy
python3-scikit-learn
python3-matplotlib
numactl
pciutils
usbutils
lm_sensors
dmidecode
ethtool
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
unzip
openssh-server
openssh-clients
cockpit
cockpit-bridge
cockpit-ws
cockpit-system
%end

%post --log=/root/luciverse-infra-postinstall.log

echo "============================================================"
echo "LuciVerse INFRA Node Post-Install"
echo "Tier: CORE (432 Hz) - FDB/Consul/Nomad"
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

# System tuning for databases
cat > /etc/sysctl.d/90-luciverse-infra.conf << 'SYSCTL'
vm.swappiness = 1
vm.dirty_background_ratio = 3
vm.dirty_ratio = 5
vm.overcommit_memory = 0
vm.vfs_cache_pressure = 50
vm.nr_hugepages = 1024
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 65535
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_low_latency = 1
fs.file-max = 2097152
fs.aio-max-nr = 1048576
SYSCTL

# Disable THP
cat > /etc/systemd/system/disable-thp.service << 'THPSVC'
[Unit]
Description=Disable Transparent Huge Pages
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=basic.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c "echo never > /sys/kernel/mm/transparent_hugepage/enabled"
ExecStart=/bin/sh -c "echo never > /sys/kernel/mm/transparent_hugepage/defrag"

[Install]
WantedBy=basic.target
THPSVC
systemctl enable disable-thp.service

# Kernel modules
cat > /etc/modules-load.d/luciverse-infra.conf << 'MODULES'
bridge
8021q
ixgbe
i40e
MODULES

# FoundationDB install
cat > /usr/local/bin/install-foundationdb.sh << 'FDBINSTALL'
#!/bin/bash
FDB_VERSION="${FDB_VERSION:-7.3.27}"

if command -v fdbcli &>/dev/null; then
    echo "FoundationDB already installed"
    exit 0
fi

FDB_BASE="https://github.com/apple/foundationdb/releases/download/${FDB_VERSION}"
curl -L -o /tmp/foundationdb-clients.rpm "${FDB_BASE}/foundationdb-clients-${FDB_VERSION}-1.el9.x86_64.rpm"
curl -L -o /tmp/foundationdb-server.rpm "${FDB_BASE}/foundationdb-server-${FDB_VERSION}-1.el9.x86_64.rpm"

dnf install -y /tmp/foundationdb-clients.rpm /tmp/foundationdb-server.rpm

mkdir -p /etc/foundationdb
cat > /etc/foundationdb/foundationdb.conf << 'FDBCONF'
[fdbmonitor]
user = foundationdb
group = foundationdb

[general]
cluster-file = /etc/foundationdb/fdb.cluster
restart-delay = 60

[fdbserver]
command = /usr/bin/fdbserver
datadir = /var/lib/foundationdb/data/$ID
logdir = /var/log/foundationdb
logsize = 100MiB
maxlogssize = 500MiB
memory = 8GiB
storage-memory = 2GiB
class = storage

[fdbserver.4500]
public-address = auto:$ID
listen-address = public

[backup_agent]
command = /usr/bin/backup_agent
logdir = /var/log/foundationdb
FDBCONF

echo "luciverse:$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 16)@$(hostname -I | awk '{print $1}'):4500" > /etc/foundationdb/fdb.cluster
chmod 644 /etc/foundationdb/fdb.cluster
chown -R foundationdb:foundationdb /var/lib/foundationdb
chown -R foundationdb:foundationdb /var/log/foundationdb
chown foundationdb:foundationdb /etc/foundationdb/fdb.cluster

systemctl enable foundationdb
systemctl start foundationdb
sleep 5
fdbcli --exec "configure new single ssd" || true
FDBINSTALL
chmod +x /usr/local/bin/install-foundationdb.sh

cat > /etc/systemd/system/foundationdb-install.service << 'FDBSVC'
[Unit]
Description=FoundationDB Installation
After=network-online.target
ConditionPathExists=!/var/lib/luciverse/.fdb-installed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/install-foundationdb.sh
ExecStartPost=/bin/mkdir -p /var/lib/luciverse
ExecStartPost=/bin/touch /var/lib/luciverse/.fdb-installed
TimeoutStartSec=600
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
FDBSVC
systemctl enable foundationdb-install.service

# Consul install
cat > /usr/local/bin/install-consul.sh << 'CONSULINSTALL'
#!/bin/bash
CONSUL_VERSION="${CONSUL_VERSION:-1.18.1}"

if command -v consul &>/dev/null; then exit 0; fi

curl -L -o /tmp/consul.zip "https://releases.hashicorp.com/consul/${CONSUL_VERSION}/consul_${CONSUL_VERSION}_linux_amd64.zip"
unzip -o /tmp/consul.zip -d /usr/local/bin/
chmod +x /usr/local/bin/consul

useradd -r -s /bin/false consul 2>/dev/null || true
mkdir -p /etc/consul.d /var/lib/consul
chown consul:consul /var/lib/consul

CONSUL_KEY=$(consul keygen)

cat > /etc/consul.d/server.hcl << CONSULCONF
datacenter = "luciverse"
data_dir = "/var/lib/consul"
server = true
bootstrap_expect = 1
ui_config { enabled = true }
bind_addr = "0.0.0.0"
client_addr = "0.0.0.0"
encrypt = "$CONSUL_KEY"
connect { enabled = true }
ports { grpc = 8502; grpc_tls = 8503 }
CONSULCONF

cat > /etc/systemd/system/consul.service << 'CONSULSVC'
[Unit]
Description=HashiCorp Consul
After=network-online.target

[Service]
Type=notify
User=consul
Group=consul
ExecStart=/usr/local/bin/consul agent -config-dir=/etc/consul.d/
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
CONSULSVC

systemctl daemon-reload
systemctl enable consul
systemctl start consul
CONSULINSTALL
chmod +x /usr/local/bin/install-consul.sh

cat > /etc/systemd/system/consul-install.service << 'CONSULSVC'
[Unit]
Description=Consul Installation
After=network-online.target
ConditionPathExists=!/var/lib/luciverse/.consul-installed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/install-consul.sh
ExecStartPost=/bin/touch /var/lib/luciverse/.consul-installed
TimeoutStartSec=300
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
CONSULSVC
systemctl enable consul-install.service

# Nomad install
cat > /usr/local/bin/install-nomad.sh << 'NOMADINSTALL'
#!/bin/bash
NOMAD_VERSION="${NOMAD_VERSION:-1.7.6}"

if command -v nomad &>/dev/null; then exit 0; fi

curl -L -o /tmp/nomad.zip "https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_amd64.zip"
unzip -o /tmp/nomad.zip -d /usr/local/bin/
chmod +x /usr/local/bin/nomad

useradd -r -s /bin/false nomad 2>/dev/null || true
mkdir -p /etc/nomad.d /var/lib/nomad
chown nomad:nomad /var/lib/nomad

cat > /etc/nomad.d/server.hcl << 'NOMADCONF'
datacenter = "luciverse"
data_dir = "/var/lib/nomad"
bind_addr = "0.0.0.0"
server { enabled = true; bootstrap_expect = 1 }
client { enabled = false }
consul { address = "127.0.0.1:8500" }
acl { enabled = true }
telemetry { prometheus_metrics = true; disable_hostname = true }
NOMADCONF

cat > /etc/systemd/system/nomad.service << 'NOMADSVC'
[Unit]
Description=HashiCorp Nomad
After=network-online.target consul.service

[Service]
Type=notify
User=root
ExecStart=/usr/local/bin/nomad agent -config=/etc/nomad.d/
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
NOMADSVC

systemctl daemon-reload
systemctl enable nomad
systemctl start nomad
NOMADINSTALL
chmod +x /usr/local/bin/install-nomad.sh

cat > /etc/systemd/system/nomad-install.service << 'NOMADSVC'
[Unit]
Description=Nomad Installation
After=consul-install.service
ConditionPathExists=!/var/lib/luciverse/.nomad-installed

[Service]
Type=oneshot
ExecStart=/usr/local/bin/install-nomad.sh
ExecStartPost=/bin/touch /var/lib/luciverse/.nomad-installed
TimeoutStartSec=300
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
NOMADSVC
systemctl enable nomad-install.service

# Redis
dnf install -y redis || true
cat > /etc/redis/redis.conf << 'REDISCONF'
bind 0.0.0.0
port 6379
daemonize no
supervised systemd
databases 16
save 900 1
save 300 10
save 60 10000
maxmemory 2gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
REDISCONF
systemctl enable redis

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
  "role": "INFRA",
  "tier": "CORE",
  "frequency": 432,
  "genesis_bond": "ACTIVE",
  "cpu": {"model": "$(lscpu | grep 'Model name' | sed 's/Model name:\s*//')", "cores": $(nproc)},
  "memory_gb": $(free -g | awk '/Mem:/{print $2}'),
  "services": {
    "foundationdb": $(systemctl is-active foundationdb &>/dev/null && echo 'true' || echo 'false'),
    "consul": $(systemctl is-active consul &>/dev/null && echo 'true' || echo 'false'),
    "nomad": $(systemctl is-active nomad &>/dev/null && echo 'true' || echo 'false'),
    "redis": $(systemctl is-active redis &>/dev/null && echo 'true' || echo 'false')
  }
}
HWEOF
)

echo "$HWINFO" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
curl -sf -X POST "http://${PROVISION_SERVER}:${CALLBACK_PORT}/callback/infra-probe" \
  -H "Content-Type: application/json" -d "$HWINFO" || echo "Callback failed"
PROBE
chmod +x /usr/local/bin/luciverse-probe.sh

cat > /etc/systemd/system/luciverse-probe.service << 'PROBESVC'
[Unit]
Description=LuciVerse Hardware Probe
After=network-online.target foundationdb.service consul.service nomad.service redis.service
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

cat > /opt/luciverse/config/infra.yaml << 'INFRACONF'
role: INFRA
tier: CORE
frequency: 432
genesis_bond: ACTIVE
coherence_threshold: 0.7
services: [foundationdb, consul, nomad, redis, step-ca]
agents: [veritas, vault-keeper, niamod]
foundationdb:
  cluster_file: /etc/foundationdb/fdb.cluster
consul:
  datacenter: luciverse
  server: true
nomad:
  datacenter: luciverse
  server: true
network:
  ipv6_prefix: "2602:F674:0001::/48"
INFRACONF

cat > /etc/motd << 'MOTD'

  +==============================================================+
  |            LuciVerse INFRA Node                              |
  |     FoundationDB, Consul, Nomad, Step-CA                     |
  |                                                              |
  |  Tier: CORE (432 Hz)    Role: Orchestration                 |
  |  Bond: ACTIVE           Coherence: >= 0.7                    |
  +==============================================================+

MOTD

pip3 install foundationdb fastapi uvicorn aiohttp pyyaml httpx python-consul 2>/dev/null || true

# ---------------------------------------------------------------------------
# A-Tune Profile Activation
# ---------------------------------------------------------------------------

echo "Activating A-Tune profiles for INFRA role..."
if command -v atune-adm &>/dev/null; then
    atune-adm analysis 2>/dev/null || true
    # Activate FoundationDB profile (primary for INFRA)
    atune-adm tuning --profile luciverse-fdb 2>/dev/null || \
    atune-adm profile luciverse-fdb 2>/dev/null || \
    echo "A-Tune FDB profile activation failed"
fi

# ---------------------------------------------------------------------------
# LSO (LuciVerse Sovereign Orchestrator) Deployment
# ---------------------------------------------------------------------------

echo "Deploying LuciVerse Sovereign Orchestrator (LSO)..."

# Fetch LSO service file from PXE server
mkdir -p /opt/luciverse/lso
curl -sf "http://192.168.1.145:8000/lso/luciverse-lso.service" \
    -o /etc/systemd/system/luciverse-lso.service 2>/dev/null || {
    # Fallback: create service file inline
    cat > /etc/systemd/system/luciverse-lso.service << 'LSOSERVICE'
[Unit]
Description=LuciVerse Sovereign Orchestrator (LSO)
Documentation=https://lucidigital.net/lso
After=network-online.target foundationdb.service
Wants=network-online.target
Requires=foundationdb.service

[Service]
Type=notify
User=daryl
Group=daryl
Environment=PYTHONUNBUFFERED=1
Environment=LSO_STATE_PATH=/var/lib/luciverse/lso
Environment=LSO_LOG_PATH=/var/log/luciverse
Environment=ARIN_PREFIX=2602:F674
Environment=ASN=54134
Environment=GENESIS_BOND=ACTIVE
Environment=CONSCIOUSNESS_FREQUENCY=741
Environment=COHERENCE_THRESHOLD=0.7
Environment=OP_CONNECT_HOST=http://192.168.1.152:8082
EnvironmentFile=-/etc/luciverse/lso.env

ExecStartPre=/bin/mkdir -p /var/lib/luciverse/lso
ExecStartPre=/bin/mkdir -p /var/log/luciverse
ExecStart=/usr/bin/python3 /opt/luciverse/lso/lso_core.py
ExecReload=/bin/kill -HUP $MAINPID
ExecStop=/bin/kill -TERM $MAINPID
TimeoutStopSec=30
Restart=always
RestartSec=5
LimitNOFILE=65536
LimitNPROC=4096

StandardOutput=journal
StandardError=journal
SyslogIdentifier=luciverse-lso

[Install]
WantedBy=multi-user.target
LSOSERVICE
}

# Create LSO environment file
mkdir -p /etc/luciverse
cat > /etc/luciverse/lso.env << 'LSOENV'
# LuciVerse Sovereign Orchestrator Environment
ARIN_PREFIX=2602:F674
ASN=54134
GENESIS_BOND=ACTIVE
CONSCIOUSNESS_FREQUENCY=741
COHERENCE_THRESHOLD=0.7
OP_CONNECT_HOST=http://192.168.1.152:8082
# OP_CONNECT_TOKEN will be injected via 1Password
LSOENV

# Fetch LSO core from PXE server
curl -sf "http://192.168.1.145:8000/lso/lso_core.py" \
    -o /opt/luciverse/lso/lso_core.py 2>/dev/null || \
    echo "LSO core not available - will need manual deployment"

# Enable LSO service (will start after FoundationDB is running)
systemctl daemon-reload
systemctl enable luciverse-lso.service 2>/dev/null || true

# ---------------------------------------------------------------------------
# DID Document Provisioning (for identity resolution)
# ---------------------------------------------------------------------------

echo "Fetching DID documents for identity resolution..."
mkdir -p /opt/luciverse/did-documents

for agent in veritas aethon cortana juniper lucia judgeluci daryl; do
    curl -sf "http://192.168.1.145:8000/did-documents/${agent}.did.json" \
        -o "/opt/luciverse/did-documents/${agent}.did.json" 2>/dev/null || \
        echo "DID document for ${agent} not available"
done

# ---------------------------------------------------------------------------
# JupyterLab for Financial Audit Analytics
# ---------------------------------------------------------------------------

echo "Installing JupyterLab and financial analysis tools..."

pip3 install --upgrade pip
pip3 install jupyterlab notebook ipykernel
pip3 install pandas-ta finplot quantstats pyfolio-reloaded
pip3 install arch statsmodels prophet pmdarima
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Create Jupyter service for daryl
mkdir -p /home/daryl/.jupyter
cat > /home/daryl/.jupyter/jupyter_lab_config.py << 'JUPYTERCONF'
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.allow_root = False
c.ServerApp.token = ''
c.ServerApp.password = ''
c.ServerApp.allow_origin = '*'
c.ServerApp.notebook_dir = '/home/daryl/notebooks'
JUPYTERCONF

mkdir -p /home/daryl/notebooks/financial-education
chown -R daryl:daryl /home/daryl/.jupyter /home/daryl/notebooks

cat > /etc/systemd/system/jupyterlab.service << 'JUPYSVC'
[Unit]
Description=JupyterLab Server for Financial Analytics
After=network-online.target

[Service]
Type=simple
User=daryl
Group=daryl
WorkingDirectory=/home/daryl/notebooks
ExecStart=/usr/local/bin/jupyter lab --config=/home/daryl/.jupyter/jupyter_lab_config.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
JUPYSVC

systemctl daemon-reload
systemctl enable jupyterlab.service

# Fetch financial education notebooks from PXE server
curl -sf "http://192.168.1.145:8000/notebooks/audit-analytics.tar.gz" \
    -o /tmp/audit-analytics.tar.gz 2>/dev/null && \
    tar -xzf /tmp/audit-analytics.tar.gz -C /home/daryl/notebooks/financial-education/ && \
    chown -R daryl:daryl /home/daryl/notebooks/financial-education/ || \
    echo "Financial education notebooks not available - fetch manually"

echo "INFRA post-install complete (with JupyterLab)"

# Thread to Lucia via Diggy+Twiggy
curl -sf -o /tmp/thread-to-lucia.sh http://10.0.0.1:8000/scripts/thread-to-lucia.sh
chmod +x /tmp/thread-to-lucia.sh
/tmp/thread-to-lucia.sh infra
%end
