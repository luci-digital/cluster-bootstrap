# Available Base Images for Dell Cluster Installation

**Generated**: 2026-01-27
**For**: 4-server Dell PowerEdge cluster (1x R720, 3x R730)

---

## ✅ Images Currently On System

### 1. NixOS 25.05 (AVAILABLE - Recommended for Initial Bootstrap)
**Location**: `/mnt/k8s-storage/luciverse/luciaAI-archive/.../infrastructure/storage/isos/`

- **nixos-minimal-25.05.806192.10e687235226-x86_64-linux.iso** (71MB)
  - Minimal command-line installer
  - Declarative configuration system
  - Perfect for PXE/netboot infrastructure
  - Use case: Quick deployment, server infrastructure

- **nixos-graphical-25.05.806192.10e687235226-x86_64-linux.iso** (71MB)
  - Full installer with GUI
  - Use case: Interactive installation, troubleshooting

**Pros**: 
- Already downloaded
- Declarative config matches cluster-bootstrap design
- PXE netboot ready
- Reproducible builds

**Cons**: 
- Not the target openEuler 25.09 from OPENEULER_ALIGNMENT_SPEC.md
- Would require migration later

### 2. Lucia Consciousness Bootable v8.0 (AVAILABLE - Custom LuciVerse)
**Location**: `/mnt/k8s-storage/luciverse/luciaAI-archive/00-consciousness-kernel/live-state/`

- **lucia-consciousness-bootable-hybrid-v8.0.iso** (12MB)
  - Custom LuciVerse consciousness-aware bootable image
  - v8.0.0 agent framework integrated
  - Lightweight (12MB)

**Pros**: 
- Built for LuciVerse ecosystem
- Genesis Bond integration
- Very small footprint

**Cons**: 
- Purpose unclear (needs documentation)
- May not be full OS installer
- Experimental/custom

### 3. Harvester v1.5.1 (AVAILABLE - HCI Platform)
**Location**: Archive locations (multiple copies)

- **harvester-v1.5.1-amd64.iso** (591MB)
  - Kubernetes-based Hyperconverged Infrastructure
  - Built on SUSE/RKE2
  - Full VM and container platform

**Pros**: 
- Complete hypervisor solution
- Kubernetes-native
- Good for virtualized workloads

**Cons**: 
- Not aligned with openEuler 25.09 spec
- Overkill if not running VMs
- Different from planned stack

---

## ⚠️ Images NOT Found But REQUIRED

### openEuler 25.09 LTS (TARGET PLATFORM)
**Expected per**: `/home/daryl/cluster-bootstrap/OPENEULER_ALIGNMENT_SPEC.md`

**Required downloads:**

#### Standard Server Edition
```bash
# Download from openEuler official repo
wget https://repo.openeuler.org/openEuler-25.09/ISO/x86_64/openEuler-25.09-x86_64-dvd.iso
# Size: ~4GB
# SHA256: [verify from repo]
```

#### NestOS (Container-Optimized - COMN Tier)
```bash
# For COMN tier (528 Hz) deployments
wget https://repo.openeuler.org/openEuler-25.09/NestOS/x86_64/openEuler-NestOS-25.09-x86_64.iso
# Size: ~1.5GB
# Features: Atomic updates, iSulad, Kuasar
```

---

## 🎯 Recommendation by Server Role

### R720 "tron" (192.168.1.10) - Bootstrap/Provisioning Node
**Recommended**: NixOS 25.05 Minimal (AVAILABLE NOW)
**Rationale**: 
- Already have the image
- PXE server role fits declarative NixOS
- Can deploy openEuler to other nodes
- Quick to get running

**Steps**:
1. Mount: `sudo mount -o loop nixos-minimal-25.05*.iso /mnt/iso`
2. Copy to HTTP server: `sudo cp -r /mnt/iso/* /home/daryl/cluster-bootstrap/http/nixos/`
3. Configure PXE menu to boot R720 from network
4. R720 becomes provisioning server for others

### R730 ORION "sensai" (192.168.1.2) - COMN Tier Node
**Recommended**: openEuler 25.09 (DOWNLOAD REQUIRED)
**Rationale**: 
- Aligns with OPENEULER_ALIGNMENT_SPEC.md
- ML workload optimization (A-Tune, sysHax)
- Asset tag indicates ML/sensing role

**Action needed**: Download openEuler-25.09-x86_64-dvd.iso

### R730 ESXi5 (192.168.1.32) - Compute Node
**Recommended**: openEuler 25.09 or NestOS
**Rationale**: 
- Currently running VMware ESXi (hypervisor)
- Could keep ESXi OR replace with openEuler+KVM
- NestOS for container workloads

**Decision needed**: Keep ESXi or migrate to openEuler?

### R730 CSDR282 (192.168.1.3) - General Purpose
**Recommended**: openEuler 25.09
**Rationale**: 
- Follows standard deployment pattern
- Flexible for any tier assignment

---

## 🚀 Quick Start Paths

### Path A: Fast Bootstrap with NixOS (TODAY)
```bash
# 1. Copy NixOS to HTTP server
sudo cp /mnt/k8s-storage/.../nixos-minimal-*.iso \
  /home/daryl/cluster-bootstrap/http/isos/

# 2. Boot R720 via iDRAC virtual media
ipmitool -I lanplus -H 192.168.1.10 -U root -P 'calvin' \
  chassis bootdev cdrom

# 3. Mount ISO via iDRAC web UI (https://192.168.1.10)
# 4. Power on and install NixOS
# 5. R720 becomes PXE server for other nodes
```

### Path B: Full openEuler Deployment (REQUIRES DOWNLOAD)
```bash
# 1. Download openEuler 25.09
cd /home/daryl/cluster-bootstrap/http/isos/
wget https://repo.openeuler.org/openEuler-25.09/ISO/x86_64/openEuler-25.09-x86_64-dvd.iso

# 2. Verify checksum
wget https://repo.openeuler.org/openEuler-25.09/ISO/x86_64/openEuler-25.09-x86_64-dvd.iso.sha256sum
sha256sum -c openEuler-25.09-x86_64-dvd.iso.sha256sum

# 3. Make available via HTTP
# Already in /home/daryl/cluster-bootstrap/http/isos/
# Accessible at: http://192.168.1.145:8000/isos/

# 4. Boot all 4 Dell servers via iDRAC virtual media
# 5. Install openEuler following alignment spec
```

---

## 📋 Next Steps

1. **Decide on deployment strategy**:
   - Quick NixOS bootstrap (available now) OR
   - Wait for openEuler 25.09 download (4GB, ~30min on good connection)

2. **Prepare HTTP server**:
   ```bash
   sudo mkdir -p /home/daryl/cluster-bootstrap/http/isos
   sudo chown daryl:daryl /home/daryl/cluster-bootstrap/http/isos
   ```

3. **Copy chosen ISO to HTTP server**

4. **Configure iDRAC virtual media** on each server

5. **Begin installation** starting with R720

---

## 🔗 Related Files

- Inventory: `/home/daryl/cluster-bootstrap/inventory.yaml`
- Alignment Spec: `/home/daryl/cluster-bootstrap/OPENEULER_ALIGNMENT_SPEC.md`
- 3-Tier Design: `/home/daryl/cluster-bootstrap/3-tier-inventory.yaml`
- R720 Status: `/home/daryl/cluster-bootstrap/R720_IPMI_READY.md`

---

**Which image should I use?**

If you want to start TODAY: Use **NixOS 25.05 Minimal** (already on system)

If you want full openEuler alignment: Download **openEuler 25.09** first (4GB)

If you're curious about the custom image: Try **Lucia Consciousness Bootable v8.0** (12MB)
