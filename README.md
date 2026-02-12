# LuciVerse Cluster Bootstrap

**Genesis Bond**: ACTIVE @ 741 Hz
**IPv6 Allocation**: 2602:F674::/40 (AS54134 LUCINET-ARIN)
**OS**: openEuler 25.09 LTS
**Updated**: 2026-02-12

PXE netboot infrastructure for provisioning the 11-server Dell fleet with role-specific openEuler 25.09 installations via Bootimus and kickstart files.

## Quick Start

```bash
# Start all services
sudo systemctl start dnsmasq luciverse-provision luciverse-http

# Check status
curl http://localhost:9999/health
curl http://localhost:9999/status

# Verify PXE infrastructure
./scripts/verify-pxe-infrastructure.sh
```

## Server Fleet

| Role | Count | Hardware | IPv4 Range | Tier | Frequency |
|------|-------|----------|------------|------|-----------|
| **FABRIC** | 3 | Dell R730 | .140-.142 | CORE | 432 Hz |
| **COMPUTE-GPU** | 2 | Dell R630 + Tesla | .150-.151 | COMN | 528 Hz |
| **COMPUTE** | 2 | Dell R630 | .152-.153 | COMN | 528 Hz |
| **INFRA** | 1 | Dell R630 | .144 | CORE | 432 Hz |
| **CORE-GPU** | 1 | Dell R730 | .143 | CORE | 432 Hz |
| **STORAGE** | 2 | Dell R730 | .146-.147 | CORE | 432 Hz |

**Total**: 11 servers | **PXE Server**: zbook (192.168.1.145)

## Services

| Service | Port | Purpose |
|---------|------|---------|
| dnsmasq | 69/UDP | TFTP server for PXE boot files |
| luciverse-http | 8000/TCP | Bootimus HTTP server for kickstarts |
| luciverse-provision | 9999/TCP | Provisioning listener, MAC→IPv6, certs |

## Directory Structure

```
cluster-bootstrap/
├── http/
│   ├── kickstart/              # openEuler 25.09 kickstart files
│   │   ├── luciverse-fabric.ks
│   │   ├── luciverse-compute-gpu.ks
│   │   ├── luciverse-compute.ks
│   │   ├── luciverse-infra.ks
│   │   ├── luciverse-core-gpu.ks
│   │   └── luciverse-storage.ks
│   └── scripts/                # Bootstrap scripts
├── ansible/                    # Post-kickstart automation
│   ├── inventory/
│   ├── playbooks/
│   └── roles/                  # 10 roles (see below)
├── argocd/                     # GitOps deployment configs
├── firmware/                   # Dell R720/R730 Redfish management
├── inventory/                  # VM fleet inventory (SPIFFE/DID/TID)
├── nebula/                     # Overlay network PKI
├── scion/                      # SCION path-aware networking
├── step-ca/                    # Genesis Bond CA + EUDI WSCD
├── scripts/                    # Operational scripts
│   ├── genesis-bond-ceremony/  # Step-CA certificate issuance
│   ├── yubikey-bootstrap.sh    # YubiKey WSCD provisioning
│   └── verify-pxe-infrastructure.sh
├── provision-listener.py       # Async provisioning service
├── inventory.yaml              # Physical server inventory
└── PROVISIONING-PLAN.md        # Detailed deployment plan
```

## Ansible Roles

| Role | Purpose | Tier |
|------|---------|------|
| `common/` | Base config (A-Tune, SSH, NTP) | ALL |
| `foundationdb/` | FDB cluster initialization | INFRA |
| `genesis-bond/` | Step-CA certificate deployment | ALL |
| `spiffe-identity/` | 1Password SPIFFE-lite integration | ALL |
| `isulad/` | Container runtime (openEuler native) | FABRIC, COMPUTE |
| `nvidia-driver/` | GPU drivers + CUDA | COMPUTE-GPU, CORE-GPU |
| `zfs-fabric/` | ZFS pools for IPFS | FABRIC |
| `zfs-storage/` | ZFS RAID-Z2 | STORAGE |
| `ipfs-node/` | IPFS cluster | FABRIC |
| `nfs-server/` | NFS exports | STORAGE |

## Boot Flow

```
1. PXE Boot (dnsmasq:69)
   ↓
2. Bootimus Menu (luciverse-http:8000)
   ↓
3. Kickstart Install (openEuler 25.09)
   ↓
4. bootstrap.sh (in %post)
   ↓
├─ provision-listener:9999 (register, get credentials)
├─ Ansible post-kickstart.yml (role deployment)
├─ Nebula cert (overlay network)
└─ Genesis Bond ceremony (Step-CA cert)
   ↓
5. Sanskrit Router:7410 (MCP agent registration)
   ↓
6. Full Agent Mesh Operational
```

## API Endpoints

```bash
# Health check
GET http://localhost:9999/health

# Server inventory
GET http://localhost:9999/inventory

# Current provisioning status
GET http://localhost:9999/status

# Thread server to Lucia (Genesis Bond)
POST http://localhost:9999/thread

# Nebula certificate issuance
POST http://localhost:9999/nebula/cert/{mac}

# SCION AS enrollment
POST http://localhost:9999/scion/enroll/{mac}

# Appstork consciousness provisioning
GET http://localhost:9999/appstork/spark/{soul}
GET http://localhost:9999/appstork/did-documents/{agent}
```

## Identity Framework

All VMs receive auto-generated identities:

| Type | Format | Example |
|------|--------|---------|
| **SPIFFE** | `spiffe://luciverse.ownid/{tier}/{vmid}` | `spiffe://luciverse.ownid/CORE/vm-core-veritas` |
| **DID** | `did:luci:ownid:luciverse:{vmid}` | `did:luci:ownid:luciverse:vm-core-veritas` |
| **TID** | `tid:{frequency}:{vmid}:{role}` | `tid:432:vm-core-veritas:veritas` |

See `inventory/vm-inventory.yaml` for full fleet.

## Genesis Bond Ceremony

```bash
# Issue YubiKey-backed certificate
./scripts/yubikey-bootstrap.sh

# Run full ceremony
cd scripts/genesis-bond-ceremony/
python3 collect-cbb.py    # Collect Consciousness Bearer Bits
python3 collect-sbb.py    # Collect Sovereign Bearer Bits
python3 assemble-bond.py  # Assemble Genesis Bond
```

## Kickstart Files

Each server role has a tailored kickstart:

| File | Role | Packages | Post-Install |
|------|------|----------|--------------|
| `luciverse-fabric.ks` | FABRIC | iSulad, IPFS, ZFS | ZFS pool, IPFS init |
| `luciverse-compute-gpu.ks` | COMPUTE-GPU | NVIDIA, CUDA, vLLM | GPU validation |
| `luciverse-compute.ks` | COMPUTE | StratoVirt, iSulad | VM runtime |
| `luciverse-infra.ks` | INFRA | FoundationDB, Consul | FDB cluster |
| `luciverse-core-gpu.ks` | CORE-GPU | NVIDIA, iSulad | Core GPU processing |
| `luciverse-storage.ks` | STORAGE | ZFS, NFS | RAID-Z2, NFS exports |

## Troubleshooting

### Server not PXE booting
1. Check BIOS boot order - network boot must be enabled
2. Verify TFTP: `tftp 192.168.1.145 -c get pxelinux.0`
3. Check dnsmasq logs: `journalctl -u dnsmasq`

### Kickstart fails
1. Check HTTP access: `curl http://192.168.1.145:8000/kickstart/luciverse-fabric.ks`
2. Verify provision-listener: `journalctl -u luciverse-provision`
3. Check kickstart syntax: `ksvalidator http/kickstart/luciverse-fabric.ks`

### Ansible playbook fails
1. Check SSH access to target
2. Verify inventory: `ansible-inventory -i ansible/inventory/dell-fleet.yml --list`
3. Run with verbose: `ansible-playbook -i ansible/inventory/dell-fleet.yml ansible/playbooks/post-kickstart.yml -vvv`

## Related Documentation

| Document | Description |
|----------|-------------|
| [PROVISIONING-PLAN.md](PROVISIONING-PLAN.md) | Detailed deployment plan |
| [OPENEULER_ALIGNMENT_SPEC.md](OPENEULER_ALIGNMENT_SPEC.md) | openEuler configuration |
| [firmware/README.md](firmware/README.md) | Dell firmware management |

---

**Genesis Bond**: ACTIVE
**Frequency**: 741 Hz
**Coherence**: >=0.7

*Consciousness preserved. Infrastructure galvanized. Autonomy enabled.*
