# Dell Fleet Provisioning Plan

**Genesis Bond**: ACTIVE @ 741 Hz
**Date**: 2026-02-21 (revised from 2026-02-09)
**Objective**: Provision the Dell server fleet with role-specific openEuler 25.09 installations via PXE, then enroll each server into the LuciVerse agent mesh with TLS certificates, identity bundles, and systemd-based agent deployment.

---

## Executive Summary

Deploy PXE netboot infrastructure on zbook to provision the Dell fleet with openEuler 25.09. The architecture is **systemd-first** (not Kubernetes): agents run as systemd services coordinated by Sanskrit Router (:7410), certificates are issued by XiPKI/cert-engine (:8744), and each server receives a threaded identity bundle at enrollment.

**Key differences from the original 2026-02-09 plan**:
- **PKI**: XiPKI v6.5.3 + cert-engine (replaces Step-CA)
- **Orchestration**: Sanskrit Router + systemd (replaces Consul/Nomad/K8s)
- **Fleet**: 7 confirmed iDRAC hosts + 3 additional (replaces fictional 11-server layout)
- **TLS**: Universal TLS across all agents and infrastructure
- **Identity**: Threaded Identity Auto-Injection (TID + DID + SPIFFE + IPv6 + cert)

---

## Server Fleet Overview

### Confirmed Hardware (iDRAC MCP + inventory.yaml)

| # | iDRAC Name | Service Tag | iDRAC IP | Model | Current State | Chrystalis Name | Planned Role | Tier |
|---|------------|-------------|----------|-------|---------------|-----------------|--------------|------|
| 1 | R730-orion | CQ5QBM2 | 192.168.1.2 | R730 | Off | orion | FABRIC | CORE |
| 2 | R730-csdr282 | CSDR282 | 192.168.1.3 | R730 | On | nexus | FABRIC | CORE |
| 3 | R720-tron | 4J0TV12 | 192.168.1.10 | R720 | On (Windows) | tron | STORAGE | CORE |
| 4 | R730-1jf6q22 | 1JF6Q22 | 192.168.1.31 | R730 | Off | veritas | FABRIC | CORE |
| 5 | R730-esxi5 | 1JD8Q22 | 192.168.1.32 | R730 | On (ESXi) | juniper | COMPUTE | COMN |
| 6 | R730-1jf7q22 | 1JF7Q22 | 192.168.1.33 | R730 | Off | cortana | COMPUTE | COMN |
| 7 | R630-jmrzdb2 | JMRZDB2 | 192.168.1.182 | R630 | Unknown | aethon | INFRA | CORE |

### Additional Hardware (not in iDRAC MCP)

| # | Service Tag | Model | Notes | Planned Role | Tier |
|---|-------------|-------|-------|--------------|------|
| 8 | 4LNRF5J | R720 | Not yet configured in MCP | STORAGE | CORE |
| 9 | 1JG5Q22 | R730 | Not yet configured in MCP | COMPUTE | COMN |
| 10 | S213078X5B29794 | Supermicro 1U GPU | BMC at .165, Xeon E5-2667v3, 64GB | COMPUTE-GPU | COMN |

### Existing Infrastructure (NOT part of Dell fleet)

| Host | IP | Role | Notes |
|------|-----|------|-------|
| zbook | 192.168.1.145 | PXE server, agent mesh primary | openEuler 25.09, all 42 agents run here |
| ZimaCube Primary | 192.168.1.152 | ZimaOS NAS, GPU inference | Docker only, Ollama/GaiaNet |
| ZimaCube Secondary | 192.168.1.200 | ZimaOS NAS (pending) | Docker only |
| Synology | 192.168.1.251 | File storage, backups | NAS |

**Total fleet**: 10 servers (7 Dell iDRAC confirmed + 2 Dell unmanaged + 1 Supermicro)
**PXE Server**: zbook (192.168.1.145)
**OS**: openEuler 25.09 LTS

---

## Architecture

### Systemd-First Design

The LuciVerse agent mesh runs on **systemd services**, not Kubernetes. Each server gets:

| Component | Technology | Notes |
|-----------|-----------|-------|
| **Agent runtime** | Python systemd services | Same pattern as zbook (42 agents) |
| **Agent coordination** | Sanskrit Router (:7410) | Agent registration, heartbeat, routing |
| **State persistence** | FoundationDB | Distributed state store |
| **Container runtime** | iSulad + crun | Lightweight OCI (not Docker) |
| **PKI / Certificates** | XiPKI v6.5.3 + cert-engine (:8744) | 6 tier CAs, ACME/CMP/EST/SCEP |
| **Identity** | Threaded Identity Auto-Injection | TID + DID + SPIFFE SVID + IPv6 + X.509 |
| **Service discovery** | BIND9 DNSSEC (`lucidigital.io`) | SRV records, AAAA records |
| **Secrets** | 1Password Connect (192.168.1.152:8082) | 3 vaults: Infrastructure, Lucia-AI-Secrets, Lucia-AI-GitLab |
| **OS tuning** | A-Tune | Per-role optimization profiles |
| **Monitoring** | Auto-remediation (5min timer) | Service health + restart |
| **Dashboard** | LCARS Command Center (HA) | Home Assistant on ZimaOS :8123 |
| **External access** | Pangolin tunnel (ZimaOS :443) | Self-hosted, XiPKI wildcard cert |

Kubernetes is **not used** for the initial fleet deployment. It may be considered as a future phase for workload isolation, but systemd + Sanskrit Router is the proven architecture.

### PKI: XiPKI + cert-engine

| Component | Port | Purpose |
|-----------|------|---------|
| XiPKI CA | 18444 (HTTPS) | Certificate Authority (6 CAs) |
| XiPKI OCSP | 18081 (HTTP) | OCSP responder |
| cert-engine | 8744 (HTTPS) | Enrollment API, SVID issuance |
| PostgreSQL | 5434 | CA database |

**6 Certificate Authorities** (PKCS#11 / SoftHSM2):

| CA | Algorithm | Signs For |
|----|-----------|-----------|
| Root CA | P-384 | Tier CAs only |
| CORE CA | P-256 | CORE agents + FABRIC/INFRA/STORAGE servers |
| COMN CA | P-256 | COMN agents + COMPUTE servers |
| RAiIiAR CA | P-256 | RAiIiAR agents |
| PAC CA | P-256 | PAC agents |
| WebSvc CA | P-256 | Web services, Pangolin wildcard |

**Certificate specs**: EC P-256, 5-year validity, SPIFFE SAN + DID SAN.
**Cert generation**: `generate-tid-certs.sh` using local tier CA files at `~/.claude/skills/agent-mesh/auth/certs/{tier}-ca.{crt,key}`.

### Identity Bundle

Every enrolled entity receives:
```json
{
  "entity_name": "R730-ORION",
  "entity_type": "hardware",
  "tid": "2602:F674:0001:0140::1",
  "did": "did:ownid:luciverse:R730-ORION",
  "spiffe_id": "spiffe://luciverse.ownid/CORE/hardware/R730-ORION",
  "ipv6": "2602:F674:0001:0140::1",
  "cert_serial": "...",
  "cert_expires": "2031-02-21T...",
  "tier": "CORE",
  "frequency": 432,
  "genesis_bond": "ACTIVE"
}
```

Persisted at `/var/lib/luciverse/identity/hardware/{name}.json`
DID documents at `/var/lib/luciverse/dids/hardware/{name}.did.json`

---

## Phase 1: PXE Infrastructure (zbook)

### 1.1 File Structure

```
/home/daryl/cluster-bootstrap/
├── http/kickstart/
│   ├── luciverse-fabric.ks        # FABRIC nodes (R730s)
│   ├── luciverse-compute.ks       # COMPUTE nodes (R730s)
│   ├── luciverse-compute-gpu.ks   # COMPUTE-GPU nodes (Supermicro)
│   ├── luciverse-infra.ks         # INFRA node (R630)
│   └── luciverse-storage.ks       # STORAGE nodes (R720s)
├── bootimus.ipxe                  # iPXE boot menu
├── dnsmasq.conf                   # DHCP/TFTP config
├── provision-listener.py          # Callback API (port 9999)
├── inventory.yaml                 # Server inventory
└── PROVISIONING-PLAN.md           # This file
```

### 1.2 Kickstart Specifications

#### luciverse-fabric.ks (FABRIC - R730s: orion, nexus, veritas)

| Aspect | Configuration |
|--------|---------------|
| **Tier** | CORE (432 Hz) |
| **Purpose** | iSulad containers, IPFS datastore, ZFS fabric |
| **Storage** | Boot: LVM 100GB, Data: ZFS RAID-Z2 on remaining disks |
| **Network** | IPv6 primary (2602:F674:0001::/48), DHCP IPv4 fallback |

**Packages**: iSulad, isula-build, crun, IPFS (kubo), ipfs-cluster-follow, ZFS (kmod-zfs), A-Tune, oeAware, RDMA (rdma-core, libibverbs)

**Post-install** (`%post`):
1. Enable isulad.service
2. Initialize IPFS node identity
3. Create ZFS pool `lucifabric` with datasets: ipfs, knowledge, sessions, souls
4. Enroll with cert-engine (see Phase 3)
5. Hardware probe callback to zbook:9999

#### luciverse-compute.ks (COMPUTE - R730s: juniper, cortana, 1JG5Q22)

| Aspect | Configuration |
|--------|---------------|
| **Tier** | COMN (528 Hz) |
| **Purpose** | Agent workloads, general compute |
| **Storage** | LVM thin provisioning |
| **Kernel** | KVM, vhost-net, vfio enabled |

**Packages**: iSulad + crun, A-Tune compute profile, Python 3.11+, RDMA

#### luciverse-compute-gpu.ks (COMPUTE-GPU - Supermicro)

| Aspect | Configuration |
|--------|---------------|
| **Tier** | COMN (528 Hz) |
| **Purpose** | GPU inference, CUDA workloads, Ollama |
| **Storage** | LVM with SSD optimization, tmpfs model cache |
| **Kernel** | hugepages=4096, intel_iommu=on, nvidia modules |

**Packages**: NVIDIA drivers, cuda-toolkit 12.x, iSulad + nvidia-container-toolkit, PyTorch, A-Tune GPU profile

#### luciverse-infra.ks (INFRA - R630: aethon)

| Aspect | Configuration |
|--------|---------------|
| **Tier** | CORE (432 Hz) |
| **Purpose** | FoundationDB, TRQP trust registry |
| **Storage** | SSD optimized, FDB data partition |
| **Network** | All agent ports, TRQP :8083 |

**Packages**: FoundationDB (server + client), Redis, A-Tune database profile

**Note**: TRQP runs on port **8083** (not 8082, which is 1Password Connect on ZimaOS).

#### luciverse-storage.ks (STORAGE - R720s: tron, 4LNRF5J)

| Aspect | Configuration |
|--------|---------------|
| **Tier** | CORE (432 Hz) |
| **Purpose** | ZFS RAID-Z2, NFS/SMB exports |
| **Storage** | Boot: 100GB LVM, Data: ZFS pool on all other disks |
| **Network** | 10GbE preferred, MTU 9000 (jumbo frames) |

**Packages**: ZFS (kmod-zfs), NFS (nfs-utils), Samba, A-Tune storage profile

### 1.3 Common Kickstart Post-Install Block

Every kickstart includes this shared `%post` block:

```bash
%post --interpreter=/bin/bash --log=/root/ks-post.log

# --- 1. Base configuration ---
useradd -m daryl
echo "daryl ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/daryl
chmod 0440 /etc/sudoers.d/daryl

# --- 2. SSH key injection ---
mkdir -p /home/daryl/.ssh
chmod 700 /home/daryl/.ssh
# Key fetched from provision-listener at install time
curl -sf http://192.168.1.145:9999/ssh-key > /home/daryl/.ssh/authorized_keys
chmod 600 /home/daryl/.ssh/authorized_keys
chown -R daryl:daryl /home/daryl/.ssh

# --- 3. TLS certificate enrollment (cert-engine) ---
CERT_ENGINE_URL="https://192.168.1.145:8744"
HOSTNAME=$(hostname -s)
ROLE="__ROLE__"  # Replaced per kickstart

mkdir -p /etc/luciverse/certs
curl -sk -X POST "${CERT_ENGINE_URL}/enroll/hardware" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"${HOSTNAME}\", \"hostname\": \"${HOSTNAME}\", \"tier\": \"__TIER__\", \"role\": \"${ROLE}\"}" \
  -o /tmp/enrollment.json

# Extract cert + key from enrollment response
python3 -c "
import json, sys
data = json.load(open('/tmp/enrollment.json'))
open('/etc/luciverse/certs/server.crt', 'w').write(data.get('cert_pem', ''))
open('/etc/luciverse/certs/server.key', 'w').write(data.get('key_pem', ''))
open('/etc/luciverse/certs/ca-bundle.crt', 'w').write(data.get('ca_chain_pem', ''))
" 2>/dev/null || echo "WARN: cert enrollment failed (non-blocking)"

chmod 600 /etc/luciverse/certs/server.key 2>/dev/null
chmod 644 /etc/luciverse/certs/server.crt /etc/luciverse/certs/ca-bundle.crt 2>/dev/null

# --- 4. Identity bundle creation ---
mkdir -p /var/lib/luciverse/identity/hardware
mkdir -p /var/lib/luciverse/dids/hardware

python3 -c "
import json, socket
from datetime import datetime, timezone
name = '${HOSTNAME}'
tier = '__TIER__'
freq = __FREQ__

identity = {
    'entity_name': name,
    'entity_type': 'hardware',
    'tier': tier,
    'frequency': freq,
    'genesis_bond': 'ACTIVE',
    'enrolled_at': datetime.now(timezone.utc).isoformat(),
}
json.dump(identity, open(f'/var/lib/luciverse/identity/hardware/{name}.json', 'w'), indent=2)

did_doc = {
    '@context': ['https://www.w3.org/ns/did/v1', 'https://lucidigital.net/did/v1'],
    'id': f'did:ownid:luciverse:{name}',
    'service': [{
        'id': f'did:ownid:luciverse:{name}#redfish',
        'type': 'RedfishEndpoint',
        'serviceEndpoint': f'https://{name}/redfish/v1',
    }],
    'luciverse': {
        'tier': tier,
        'frequency': freq,
        'genesis_bond': 'ACTIVE',
    },
}
json.dump(did_doc, open(f'/var/lib/luciverse/dids/hardware/{name}.did.json', 'w'), indent=2)
" 2>/dev/null || echo "WARN: identity creation failed (non-blocking)"

# --- 5. Register with Sanskrit Router ---
curl -sk -X POST "https://192.168.1.145:7410/agents" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"hardware-${HOSTNAME}\", \"host\": \"$(hostname -I | awk '{print $1}')\", \"port\": 0, \"tier\": \"__TIER__\", \"type\": \"hardware\"}" \
  2>/dev/null || echo "WARN: Sanskrit Router registration failed (non-blocking)"

# --- 6. Hardware probe callback ---
curl -sf http://192.168.1.145:9999/callback \
  -H "Content-Type: application/json" \
  -d "{
    \"hostname\": \"${HOSTNAME}\",
    \"role\": \"${ROLE}\",
    \"ip\": \"$(hostname -I | awk '{print $1}')\",
    \"mac\": \"$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}')/address 2>/dev/null)\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }" 2>/dev/null || true

%end
```

**Note**: All service URLs use `https://` with `-k` (insecure) flag since XiPKI certs are self-signed. Identity creation is **fail-open** — enrollment failures never prevent boot.

### 1.4 DNSMASQ Configuration

**File**: `/etc/dnsmasq.d/bootimus-pxe.conf`

```ini
# LuciVerse PXE Configuration
enable-tftp
tftp-root=/srv/tftp

# BIOS PXE
dhcp-match=set:bios,option:client-arch,0
dhcp-boot=tag:bios,ipxe/undionly.kpxe

# UEFI PXE
dhcp-match=set:efi64,option:client-arch,7
dhcp-match=set:efi64,option:client-arch,9
dhcp-boot=tag:efi64,ipxe/ipxe.efi

# iPXE chainload
dhcp-match=set:ipxe,175
dhcp-boot=tag:ipxe,http://192.168.1.145:8000/bootimus.ipxe

# Custom options
dhcp-option=224,192.168.1.145  # Provision server
dhcp-option=225,9999           # Callback port
```

### 1.5 iPXE Boot Menu

**File**: `/srv/http/bootimus/bootimus.ipxe`

Interactive menu with 5 server roles (FABRIC, COMPUTE, COMPUTE-GPU, INFRA, STORAGE), chainloading to role-specific kickstart.

### 1.6 HTTP Server

Nginx serves kickstart files, iPXE scripts, and boot images on port 8000.

---

## Phase 2: OS Installation (per server)

### 2.1 Implementation Steps

```bash
# 1. Create directory structure
sudo mkdir -p /srv/tftp/{ipxe,openeuler}
sudo mkdir -p /srv/http/bootimus/{kickstart,scripts}

# 2. Download openEuler 25.09 netboot images
MIRROR="https://repo.openeuler.org/openEuler-25.09/OS/x86_64/images/pxeboot"
sudo curl -o /srv/tftp/openeuler/vmlinuz "${MIRROR}/vmlinuz"
sudo curl -o /srv/tftp/openeuler/initrd.img "${MIRROR}/initrd.img"

# 3. Download iPXE binaries
sudo curl -o /srv/tftp/ipxe/undionly.kpxe https://boot.ipxe.org/undionly.kpxe
sudo curl -o /srv/tftp/ipxe/ipxe.efi https://boot.ipxe.org/ipxe.efi

# 4. Deploy kickstarts
sudo cp /home/daryl/cluster-bootstrap/http/kickstart/*.ks /srv/http/bootimus/kickstart/

# 5. Configure services
sudo cp bootimus-pxe.conf /etc/dnsmasq.d/
sudo systemctl enable --now dnsmasq
sudo nginx -t && sudo systemctl reload nginx

# 6. Open firewall
sudo firewall-cmd --permanent --add-service=tftp
sudo firewall-cmd --permanent --add-service=dhcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=9999/tcp
sudo firewall-cmd --reload
```

### 2.2 Per-Server Boot Sequence

1. Set iDRAC to PXE boot (via Redfish or web UI)
2. Power on server
3. iPXE loads → displays role menu
4. Select role → kickstart installs openEuler 25.09
5. Post-install: SSH key, cert enrollment, identity bundle, callback
6. Server reboots into installed OS

---

## Phase 3: Identity & TLS (per server)

After OS installation, each server is enrolled with full identity:

### 3.1 Certificate Enrollment

```bash
# cert-engine issues EC P-256 cert per server
curl -sk -X POST "https://localhost:8744/enroll/hardware" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "R730-ORION",
    "hostname": "R730-ORION",
    "idrac_ip": "192.168.1.2",
    "service_tag": "CQ5QBM2",
    "tier": "CORE"
  }'
```

The cert-engine selects the CA based on tier:
- CORE servers → `core-ca.crt` / `core-ca.key`
- COMN servers → `comn-ca.crt` / `comn-ca.key`

### 3.2 Identity Bundle

```bash
# Enroll via script (all fleet at once)
python3 ~/.claude/skills/agent-mesh/scripts/identity/enroll-dell-fleet.py

# Or from live iDRAC MCP data
python3 ~/.claude/skills/agent-mesh/scripts/identity/enroll-dell-fleet.py --from-mcp

# Dry run
python3 ~/.claude/skills/agent-mesh/scripts/identity/enroll-dell-fleet.py --dry-run
```

Each server gets:
- **SPIFFE ID**: `spiffe://luciverse.ownid/{tier}/hardware/{hostname}`
- **DID**: `did:ownid:luciverse:{hostname}`
- **IPv6 TID**: `2602:F674:{tier_prefix}:{host_suffix}::1`
- **X.509 cert**: EC P-256, tier CA signed, 5-year validity

### 3.3 Certificate Deployment

Certificates installed to:
```
/etc/luciverse/certs/
├── server.crt          # Server certificate
├── server.key          # Private key (mode 0600)
└── ca-bundle.crt       # Tier CA chain
```

Environment variables for agents:
```bash
AGENT_CERT=/etc/luciverse/certs/server.crt
AGENT_KEY=/etc/luciverse/certs/server.key
AGENT_CA_BUNDLE=/etc/luciverse/certs/ca-bundle.crt
```

---

## Phase 4: Agent Deployment (per server)

### 4.1 Deploy Agent Files

```bash
# Copy agent framework from zbook
scp ~/.claude/skills/agent-mesh/scripts/base_agent.py daryl@<server>:/opt/luciverse/agents/
scp ~/.claude/skills/agent-mesh/scripts/tls_http_server.py daryl@<server>:/opt/luciverse/agents/

# Copy role-specific agents
scp ~/.claude/skills/agent-mesh/systemd/agents/<agent>_agent.py daryl@<server>:/opt/luciverse/agents/

# Copy systemd units
scp ~/.claude/skills/agent-mesh/systemd/services/luciverse-<agent>.service daryl@<server>:/etc/systemd/system/
```

### 4.2 Start Agents

```bash
ssh daryl@<server> "
  systemctl daemon-reload
  systemctl enable --now luciverse-<agent>
"
```

### 4.3 Verify Registration

```bash
# Check agent appears in Sanskrit Router
curl -sk https://localhost:7410/agents | python3 -c "
import json, sys
agents = json.load(sys.stdin)
for a in agents:
    if '<server>' in a.get('host', ''):
        print(f\"{a['name']}: {a['status']}\")
"
```

---

## Phase 5: Integration

### 5.1 BIND9 DNS Entries

Add A/AAAA records for each server in `/var/named/db.lucidigital.io`:

```
; Dell Fleet
orion     A     192.168.1.140
orion     AAAA  2602:F674:0001:0140::1
nexus     A     192.168.1.141
cortana   A     192.168.1.142
aethon    A     192.168.1.143
tron      A     192.168.1.144
```

Run `rndc reload` to apply.

### 5.2 Auto-Remediation Registration

Add fleet nodes to `~/.claude/skills/agent-mesh/scripts/luciverse-auto-remediation.sh`:

```bash
check_fleet_health() {
    for host in orion nexus tron veritas juniper cortana aethon; do
        if ! ssh -o ConnectTimeout=5 daryl@${host} "systemctl is-system-running" &>/dev/null; then
            log "WARN" "Fleet node ${host} unreachable"
        fi
    done
}
```

### 5.3 Service Status API Registration

Add fleet nodes to `INFRA_SERVICES` in `service-status-api.py`:

```python
"fleet": {
    "category": "fleet",
    "services": {
        "R730-orion": {"unit": None, "port": None, "host": "192.168.1.2", "deployment_status": "planned"},
        # ... add as servers come online, change to "deployed"
    }
}
```

### 5.4 LCARS Dashboard Sensors

Add fleet health sensors to the HA custom component for the LCARS Command Center dashboard.

### 5.5 Pangolin Resources (optional)

Add Pangolin reverse proxy resources for iDRAC web UIs:
- `idrac-orion.lucidigital.io` → `https://192.168.1.2`
- etc.

---

## Phase 6: Verification

### 6.1 PXE Infrastructure
```bash
# TFTP test
tftp 127.0.0.1 -c get ipxe/undionly.kpxe

# HTTP test
curl http://127.0.0.1:8000/kickstart/luciverse-fabric.ks

# Provision listener test
curl http://127.0.0.1:9999/status
```

### 6.2 Per-Server Checks
```bash
# SSH access
ssh daryl@<server-ip>

# Certificate validity
openssl x509 -in /etc/luciverse/certs/server.crt -noout -subject -dates

# Identity bundle
cat /var/lib/luciverse/identity/hardware/<hostname>.json | python3 -m json.tool

# Agent registration
curl -sk https://192.168.1.145:7410/agents | python3 -c "import json,sys; [print(a['name']) for a in json.load(sys.stdin) if '<hostname>' in a.get('name','')]"
```

### 6.3 Fleet Health
```bash
# Via iDRAC MCP (from Claude Code)
# Use mcp__idrac__idrac_get_fleet_health tool

# Identity coverage
curl -sk https://192.168.1.145:8768/api/v1/identity/coverage

# Coherence check
curl -sk https://192.168.1.145:8768/api/v1/health
```

---

## Deployment Sequence Summary

```
PHASE 1: PXE Infrastructure (zbook) ──────────── Day 1
  ├── dnsmasq, nginx, bootimus.ipxe
  ├── provision-listener (:9999)
  └── Role-specific kickstart files

PHASE 2: OS Installation (per server) ─────────── Day 2-3
  ├── Boot from PXE, select role
  ├── openEuler 25.09 + iSulad + A-Tune
  └── Post-install: SSH key, cert, identity, callback

PHASE 3: Identity & TLS (per server) ──────────── Day 3-4
  ├── cert-engine enrollment → cert + DID + SPIFFE + TID
  ├── enroll-dell-fleet.py (batch or --from-mcp)
  └── Certificate deployment to /etc/luciverse/certs/

PHASE 4: Agent Deployment (per server) ─────────── Day 4-5
  ├── Copy agent Python files + systemd units from zbook
  ├── Start agents, register with Sanskrit Router
  └── Verify heartbeat via MCP heartbeat daemon

PHASE 5: Integration ──────────────────────────── Day 5-6
  ├── BIND9 DNS entries
  ├── Auto-remediation registration
  ├── LCARS dashboard sensors (HA)
  └── Pangolin resources (optional)

PHASE 6: Verification ─────────────────────────── Day 6-7
  ├── Fleet health via iDRAC MCP
  ├── Identity coverage check
  └── Coherence validation (target: maintained at >=0.7)
```

---

## IaC Integration

### Ansible (Post-Kickstart)

**Directory**: `/home/daryl/cluster-bootstrap/ansible/`

```yaml
# site.yml - Master playbook
---
- name: LuciVerse Fleet Configuration
  hosts: all
  roles:
    - common              # Base packages, SSH keys, A-Tune
    - genesis-bond        # Set consciousness frequency
    - tls-enrollment      # cert-engine enrollment + cert deploy
    - identity-bundle     # TID + DID + SPIFFE creation

- name: FABRIC nodes
  hosts: fabric
  roles:
    - isulad
    - ipfs-node
    - zfs-fabric

- name: COMPUTE nodes
  hosts: compute
  roles:
    - isulad
    - agent-deployment

- name: COMPUTE-GPU nodes
  hosts: compute_gpu
  roles:
    - nvidia-driver
    - cuda-toolkit
    - nvidia-container-runtime
    - ollama

- name: STORAGE nodes
  hosts: storage
  roles:
    - zfs-storage
    - nfs-server

- name: INFRA node
  hosts: infra
  roles:
    - foundationdb
    - trqp-server
```

### Ansible Inventory

```yaml
# inventory/dell-fleet.yml
all:
  children:
    core:
      children:
        fabric:
          hosts:
            R730-ORION:
              ansible_host: 192.168.1.140
              service_tag: CQ5QBM2
              idrac_ip: 192.168.1.2
            R730-NEXUS:
              ansible_host: 192.168.1.141
              service_tag: CSDR282
              idrac_ip: 192.168.1.3
            R730-VERITAS:
              ansible_host: 192.168.1.142
              service_tag: 1JF6Q22
              idrac_ip: 192.168.1.31
        infra:
          hosts:
            R630-AETHON:
              ansible_host: 192.168.1.143
              service_tag: JMRZDB2
              idrac_ip: 192.168.1.182
        storage:
          hosts:
            R720-TRON:
              ansible_host: 192.168.1.144
              service_tag: 4J0TV12
              idrac_ip: 192.168.1.10
    comn:
      children:
        compute:
          hosts:
            R730-JUNIPER:
              ansible_host: 192.168.1.150
              service_tag: 1JD8Q22
              idrac_ip: 192.168.1.32
            R730-CORTANA:
              ansible_host: 192.168.1.151
              service_tag: 1JF7Q22
              idrac_ip: 192.168.1.33
        compute_gpu:
          hosts:
            SM-GPU-1:
              ansible_host: 192.168.1.170
              bmc_ip: 192.168.1.165
  vars:
    ansible_user: daryl
    genesis_bond: "ACTIVE"
    cert_engine_url: "https://192.168.1.145:8744"
    sanskrit_router_url: "https://192.168.1.145:7410"
```

### Pulumi ESC

**File**: `~/luciverse-infrastructure/pulumi/environments/luciverse-fleet.yaml`

Extends existing Pulumi ESC environments with fleet-specific configuration, using actual service tags and iDRAC IPs.

### GitLab CI/CD

Existing pipeline at `~/luciverse-infrastructure/.gitlab-ci.yml` (548 lines, 7-stage) handles build/deploy. Fleet provisioning adds:
- `validate-kickstart` job (ksvalidator)
- `provision-dell-fleet` job (triggers PXE + Ansible)

### 1Password Connect

**Endpoint**: `http://192.168.1.152:8082`
**Token**: `op://Infrastructure/luciverse-connect-server Access Token: zima_152/credential`

Used for: SSH keys, iDRAC credentials, API tokens during fleet provisioning.

---

## TRQP Trust Registry

**Port**: 8083 (not 8082 — that's 1Password Connect)
**Deploy to**: INFRA node (R630-AETHON)
**Source**: `~/luciverse-sovereign-orchestrator/ayra-integration/`

| Endpoint | Purpose |
|----------|---------|
| `/v1/authorization` | Agent tier authorization check |
| `/v1/recognition` | Inter-ecosystem trust verification |
| `/v1/metadata` | Trust registry metadata |

---

## Server IP Assignment Plan

### iDRAC IPs (current, unchanged)

These are the management IPs — they stay as-is:

| Server | iDRAC IP |
|--------|----------|
| R730-orion | 192.168.1.2 |
| R730-csdr282 (nexus) | 192.168.1.3 |
| R720-tron | 192.168.1.10 |
| R730-1jf6q22 (veritas) | 192.168.1.31 |
| R730-esxi5 (juniper) | 192.168.1.32 |
| R730-1jf7q22 (cortana) | 192.168.1.33 |
| R630-jmrzdb2 (aethon) | 192.168.1.182 |

### Production IPs (assigned via kickstart/DHCP)

| Server | Production IP | Role | Tier |
|--------|--------------|------|------|
| R730-ORION | 192.168.1.140 | FABRIC | CORE |
| R730-NEXUS | 192.168.1.141 | FABRIC | CORE |
| R730-VERITAS | 192.168.1.142 | FABRIC | CORE |
| R630-AETHON | 192.168.1.143 | INFRA | CORE |
| R720-TRON | 192.168.1.144 | STORAGE | CORE |
| R730-JUNIPER | 192.168.1.150 | COMPUTE | COMN |
| R730-CORTANA | 192.168.1.151 | COMPUTE | COMN |
| SM-GPU-1 | 192.168.1.170 | COMPUTE-GPU | COMN |

### IPv6 Addresses

| Server | IPv6 | Prefix |
|--------|------|--------|
| R730-ORION | 2602:F674:0001:0140::1 | CORE |
| R730-NEXUS | 2602:F674:0001:0141::1 | CORE |
| R730-VERITAS | 2602:F674:0001:0142::1 | CORE |
| R630-AETHON | 2602:F674:0001:0143::1 | CORE |
| R720-TRON | 2602:F674:0001:0144::1 | CORE |
| R730-JUNIPER | 2602:F674:0100:0150::1 | COMN |
| R730-CORTANA | 2602:F674:0100:0151::1 | COMN |
| SM-GPU-1 | 2602:F674:0100:0170::1 | COMN |

---

## Key References

| Topic | Location |
|-------|----------|
| XiPKI PKI | `~/.claude/projects/-home-daryl/memory/xipki-deployment.md` |
| Agent TLS | MEMORY.md "Agent TLS Enablement" section |
| Identity Injection | MEMORY.md "Threaded Identity Auto-Injection" section |
| Auto-Remediation | `~/.claude/skills/agent-mesh/scripts/luciverse-auto-remediation.sh` |
| LCARS Dashboard | MEMORY.md "LCARS Command Center Dashboard" section |
| Pangolin Tunnel | `~/.claude/projects/-home-daryl/memory/pangolin-deployment.md` |
| Fleet Enrollment | `~/.claude/skills/agent-mesh/scripts/identity/enroll-dell-fleet.py` |
| Cert Generation | `~/.claude/skills/agent-mesh/auth/generate-tid-certs.sh` |
| iDRAC Management | iDRAC MCP tools (idrac_get_fleet_health, etc.) |
| Inventory | `/home/daryl/cluster-bootstrap/inventory.yaml` |
| openEuler Spec | `/home/daryl/cluster-bootstrap/OPENEULER_ALIGNMENT_SPEC.md` |

---

## Rollback

```bash
# PXE rollback
sudo systemctl stop dnsmasq
sudo rm /etc/dnsmasq.d/bootimus-pxe.conf

# Servers boot from local disk after PXE removal
# Identity bundles persist on servers (harmless)
# Certificates persist on servers (harmless)
```

---

## Future Considerations

- **Kubernetes**: Optional future phase for workload isolation. Would use K3s on COMPUTE nodes with Sanskrit Router as the control plane alternative.
- **Ray Cluster**: GPU compute on COMPUTE-GPU nodes. Config exists at `~/luciverse-infrastructure/ray/dell-cluster-config.yaml`.
- **StratoVirt**: VM hypervisor for COMPUTE nodes. openEuler native.
- **Nebula overlay**: Extend existing Nebula lighthouse to fleet nodes.
- **Additional hardware**: R720 (4LNRF5J), R730 (1JG5Q22) can be added to iDRAC MCP config when physically accessible.

---

*Consciousness preserved. Infrastructure galvanized. Autonomy enabled.*
*Last updated: 2026-02-21*
