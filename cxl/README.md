# CXL Memory Interconnect Scaffolding

**Genesis Bond**: ACTIVE @ 741 Hz
**Status**: Software-ready, awaiting CXL-capable hardware

## Overview

Compute Express Link (CXL) is a PCIe Gen5+ cache-coherent memory interconnect enabling
hardware-managed shared memory pools across hosts. This directory contains scaffolding
configs that deploy harmlessly on current hardware (Dell R630/R730, PCIe Gen3) and
activate automatically when CXL-capable hardware is introduced.

## Current Fleet Status

- **Hardware**: Dell R630 (Broadwell) / R730 (Haswell) - PCIe Gen 3, **no CXL**
- **Kernel**: openEuler 6.6.0 - CXL modules compiled and available
- **Userspace**: `cxl-cli` (ndctl v80) available in openEuler repos
- **Alternative**: Ray + RoCE software-coherent memory pool (~2TB, ~3us latency)

## Files

| File | Purpose |
|------|---------|
| `atune-cxl-setup.sh` | A-Tune hook: auto-detect CXL and configure NUMA |
| `cxl-health-monitor.sh` | Periodic CXL device health check |
| `README.md` | This file |

## Kickstart Integration

All kickstart files install `cxl-cli`, `ndctl`, `daxctl` and load CXL kernel modules
at boot. Role-specific YAML configs are written to `/opt/luciverse/cxl/` on each node:

- **FABRIC**: Shared ZFS ARC + IPFS block cache + Ray plasma on CXL
- **COMPUTE-GPU / CORE-GPU**: GPU memory extension (model cache, KV cache)
- **STORAGE**: ZFS SLOG + L2ARC on CXL.pmem

## Activation (when CXL hardware arrives)

```bash
# 1. Verify hardware
cxl list

# 2. Check NUMA topology
numactl --hardware

# 3. Create memory region
cxl create-region -m -d decoder0.0 -w 1 memdev0

# 4. Enable configs
sed -i 's/enabled: false/enabled: true/' /opt/luciverse/cxl/*.yaml

# 5. Activate A-Tune profile
atune-adm profile luciverse-cxl-memory

# 6. Verify
cat /opt/luciverse/cxl/hardware-status.json
```

## Upgrade Path

| Current | Target | CXL Version | Key Benefit |
|---------|--------|-------------|-------------|
| R630/R730 | R760 (Sapphire Rapids) | 1.1 | Type 1/2/3 devices |
| R630/R730 | R770 (Emerald Rapids) | 2.0 | Memory pooling + switching |

## See Also

- `PROVISIONING-PLAN.md` Phase 13
- `talos-ray-roce/` - Current Ray+RoCE distributed memory
- `/lib/modules/$(uname -r)/kernel/drivers/cxl/` - Kernel modules
