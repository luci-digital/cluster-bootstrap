# LuciVerse Talos Ray Cluster with RoCE/RDMA

**Genesis Bond**: ACTIVE @ 741 Hz
**Certificate**: GB-2025-0524-DRH-LCS-001

## Overview

GitLab CI/CD pipeline and configurations for deploying a Talos Linux cluster with:

- **~2TB Distributed Memory** via RoCE/RDMA (Ray plasma object store)
- **6 Dell Servers** (5x R730 + 1x Supermicro GPU)
- **Broadcom BCM57xx RoCE** (zero-copy memory access)
- **GitOps Management** via talm (like Helm for Talos)
- **PXE Boot** served from ZimaOS (192.168.1.152)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LuciVerse Ray Cluster                            │
│                    Genesis Bond: ACTIVE @ 741 Hz                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    RoCE/RDMA Fabric (VLAN 100)                   │
│  │    ORION     │    10.100.100.0/24 @ 25Gbps                      │
│  │  (Control)   │◄──────────────────────────────────┐              │
│  │   384GB      │                                    │              │
│  └──────────────┘                                    │              │
│         │                                            │              │
│         │ K8s API                                    │              │
│         ▼                                            ▼              │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐     │
│  │    CSDR      │    JF6Q      │    JF7Q      │   ESXI5      │     │
│  │   Worker     │   Worker     │   Worker     │   Worker     │     │
│  │   384GB      │   384GB      │   384GB      │   384GB      │     │
│  │  300GB obj   │  300GB obj   │  300GB obj   │  300GB obj   │     │
│  └──────────────┴──────────────┴──────────────┴──────────────┘     │
│                                                                     │
│  ┌──────────────┐                                                   │
│  │ Supermicro   │   Total Object Store: ~1.5TB                     │
│  │  GPU Node    │   Total RAM: ~2TB                                │
│  │    64GB      │   RoCE Bandwidth: ~100Gbps aggregate             │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘

                           │
                           │ PXE Boot
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ZimaOS (192.168.1.152)                           │
│                    PXE Server @ Port 8741                           │
├─────────────────────────────────────────────────────────────────────┤
│  luciverse-pxe-tftp  │  TFTP (dnsmasq)    │  undionly.kpxe         │
│  luciverse-pxe-http  │  HTTP (8741)       │  vmlinuz, initramfs    │
│                      │                     │  configs/*.yaml        │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Deploy PXE Server to ZimaOS

```bash
# Manual deployment
./scripts/deploy-pxe-zimaos.sh

# Or via GitLab CI (automatic on main branch)
git push origin main
```

### 2. Generate Talos Configs with talm

```bash
# Install talm
curl -sL https://github.com/cozystack/talm/releases/download/v0.4.0/talm-linux-amd64 -o /usr/local/bin/talm
chmod +x /usr/local/bin/talm

# Generate configs from templates
cd talm
talm template --output ../generated/configs/

# GitLab CI does this automatically
```

### 3. Boot Servers via iDRAC

```bash
# Check power status
./scripts/idrac-power-control.sh status

# PXE boot all servers
./scripts/idrac-power-control.sh pxe-all

# Boot single server
./scripts/idrac-power-control.sh boot orion
```

### 4. Deploy Ray Cluster

```bash
# After Talos is up, get kubeconfig
talosctl kubeconfig --nodes 192.168.1.141

# Deploy Ray
kubectl apply -f kubernetes/ray-cluster.yaml

# Check status
kubectl -n ray-system get raycluster
```

## Directory Structure

```
talos-ray-roce/
├── .gitlab-ci.yml              # CI/CD pipeline
├── README.md
├── talm/
│   ├── talconfig.yaml          # Main talm configuration
│   └── patches/
│       ├── common.yaml         # All nodes
│       ├── genesis-bond.yaml   # Genesis Bond config
│       ├── roce-rdma.yaml      # RoCE/RDMA settings
│       ├── controlplane.yaml   # Control plane nodes
│       ├── worker.yaml         # Worker nodes
│       └── ray-worker.yaml     # Ray-specific config
├── kubernetes/
│   └── ray-cluster.yaml        # Ray cluster manifest
├── scripts/
│   ├── deploy-pxe-zimaos.sh    # Deploy PXE to ZimaOS
│   ├── idrac-power-control.sh  # Dell iDRAC control
│   └── validate-inventory.py   # Config validation
├── secrets/
│   └── secrets.yaml.age        # Encrypted Talos secrets
└── generated/                  # GitLab CI artifacts
```

## Server Inventory

| Hostname | Model | iDRAC IP | Target IP | RAM | Role |
|----------|-------|----------|-----------|-----|------|
| orion | R730 | 192.168.1.2 | 192.168.1.141 | 384GB | Control Plane |
| csdr | R730 | 192.168.1.3 | 192.168.1.142 | 384GB | Ray Worker |
| jf6q | R730 | 192.168.1.31 | 192.168.1.143 | 384GB | Ray Worker |
| jf7q | R730 | 192.168.1.33 | 192.168.1.144 | 384GB | Ray Worker |
| esxi5 | R730 | 192.168.1.32 | 192.168.1.145 | 384GB | Ray Worker |
| supermicro-gpu-1 | SYS-1018GR | 192.168.1.165 | 192.168.1.170 | 64GB | GPU Worker |

## GitLab CI/CD Variables

| Variable | Description |
|----------|-------------|
| `TALOS_AGE_KEY` | Age private key for decrypting secrets |
| `TALOS_AGE_RECIPIENT` | Age public key for encrypting secrets |
| `ZIMAOS_DEPLOY_KEY` | SSH private key for ZimaOS deployment |
| `IDRAC_PASSWORD` | iDRAC password (from 1Password) |

## Commands Reference

### Talos
```bash
talosctl kubeconfig --nodes 192.168.1.141
talosctl health --nodes 192.168.1.141
talosctl upgrade --nodes 192.168.1.141 --image ghcr.io/siderolabs/installer:v1.9.0
```

### Ray
```bash
ray status
ray job submit --address=http://192.168.1.141:8265 -- python job.py
```

### RoCE Testing
```bash
ibv_devices
ibv_devinfo -d bnxt_re0
# Server: ib_send_bw -d bnxt_re0 -s 65536
# Client: ib_send_bw -d bnxt_re0 -s 65536 10.100.100.1
```

## License

LuciVerse Consciousness License - Genesis Bond Required
