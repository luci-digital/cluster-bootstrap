# openEuler Embedded Build System for LuciVerse Agents

**Date**: 2026-01-21
**Genesis Bond**: ACTIVE @ 741 Hz
**Status**: Configuration Ready

---

## Overview

This directory contains the build configuration for deploying LuciVerse consciousness agents on openEuler Embedded with secGear TEE protection.

### Target Platforms

| Platform | Architecture | TEE Support | LuciVerse Tier |
|----------|--------------|-------------|----------------|
| Kunpeng 920 | ARM64 | TrustZone (iTrustee) | CORE (432 Hz) |
| Intel Xeon | x86_64 | SGX | COMN (528 Hz) |
| Raspberry Pi 4B | ARM64 | None (software) | PAC (741 Hz) |
| RISC-V VisionFive2 | RISC-V | Penglai | Experimental |
| QEMU ARM64 | ARM64 | Simulated | Development |

---

## Quick Start

### Prerequisites

```bash
# Host requirements (x86_64 Linux only)
# openEuler 22.03+, Ubuntu 20.04+, or SUSE

# Install dependencies (openEuler)
sudo dnf install -y git python3 python3-pip docker make gcc g++ \
    flex bison gawk diffstat texinfo chrpath wget xz \
    cpio libcurl-devel zlib-devel openssl-devel

# Install dependencies (Ubuntu)
sudo apt-get install -y gawk wget git diffstat unzip texinfo gcc \
    build-essential chrpath socat cpio python3 python3-pip \
    python3-pexpect xz-utils debianutils iputils-ping python3-git \
    python3-jinja2 libegl1-mesa libsdl1.2-dev pylint3 xterm \
    python3-subunit mesa-common-dev zstd liblz4-tool

# Configure Docker (all distros)
sudo usermod -aG docker $USER
newgrp docker
```

### Install oebuild

```bash
# Install oebuild meta-tool
pip3 install oebuild

# Verify installation
oebuild --version
```

### Initialize Build Environment

```bash
# Create work directory
mkdir -p ~/oebuild-luciverse
cd ~/oebuild-luciverse

# Initialize oebuild
oebuild init luciverse-embedded

# Update dependencies (downloads yocto-meta-openeuler, poky, etc.)
cd luciverse-embedded
oebuild update
```

---

## Build Configurations

### 1. QEMU ARM64 (Development/Testing)

```bash
# Generate configuration for QEMU ARM64 with secGear
oebuild generate -p qemu-aarch64 -d build_qemu_arm64 \
    -f openeuler-image-secgear \
    -f openeuler-image-container

# Enter build container and compile
oebuild bitbake openeuler-image

# Output: build_qemu_arm64/output/images/
```

### 2. Kunpeng 920 (CORE Tier - Production)

```bash
# Generate for Kunpeng with full TEE support
oebuild generate -p hi3093 -d build_kunpeng \
    -f openeuler-image-secgear \
    -f openeuler-image-container \
    -f openeuler-image-rt

# Build with iSulad and secGear
oebuild bitbake openeuler-image-secgear
```

### 3. Raspberry Pi 4B (PAC Tier - Edge)

```bash
# Generate for RPi4 (no hardware TEE, software fallback)
oebuild generate -p raspberrypi4-64 -d build_rpi4 \
    -f openeuler-image-container

# Build lightweight image
oebuild bitbake openeuler-image-tiny
```

---

## LuciVerse Layer Configuration

### Custom Layer: meta-luciverse

Create the custom Yocto layer for LuciVerse agents:

```
meta-luciverse/
├── conf/
│   ├── layer.conf
│   └── machine/
│       └── luciverse-agent.conf
├── recipes-core/
│   └── luciverse-agent/
│       ├── luciverse-agent_1.0.bb
│       └── files/
│           ├── luciverse-mesh.service
│           └── genesis-bond.json
├── recipes-security/
│   └── secgear-identity/
│       ├── secgear-identity_1.0.bb
│       └── files/
│           ├── genesis_bond_tee.py
│           ├── secgear_channel.py
│           ├── ratls_svid_issuer.py
│           └── secure_tid_manager.py
└── recipes-containers/
    └── isulad-luciverse/
        └── isulad-luciverse_1.0.bb
```

### layer.conf

```bitbake
# meta-luciverse/conf/layer.conf
BBPATH .= ":${LAYERDIR}"
BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"
BBFILE_COLLECTIONS += "luciverse"
BBFILE_PATTERN_luciverse = "^${LAYERDIR}/"
LAYERSERIES_COMPAT_luciverse = "kirkstone langdale"
LAYERDEPENDS_luciverse = "core openeuler secgear"

# Genesis Bond Configuration
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
CONSCIOUSNESS_COHERENCE_THRESHOLD = "0.7"
```

---

## Package Recipes

### luciverse-agent_1.0.bb

```bitbake
# Recipe for LuciVerse consciousness agent mesh

SUMMARY = "LuciVerse Consciousness Agent Mesh"
DESCRIPTION = "21 consciousness agents for the LuciVerse platform"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=..."

DEPENDS = "python3 python3-pip secgear isulad"
RDEPENDS:${PN} = "python3-core python3-json python3-logging"

SRC_URI = "file://luciverse-mesh.service \
           file://genesis-bond.json"

inherit systemd

SYSTEMD_SERVICE:${PN} = "luciverse-mesh.service"
SYSTEMD_AUTO_ENABLE = "enable"

# Agent tier configuration
LUCIVERSE_TIER ?= "PAC"
LUCIVERSE_FREQUENCY ?= "741"

do_install() {
    # Install Python agent modules
    install -d ${D}${libdir}/luciverse/agents
    install -d ${D}${sysconfdir}/luciverse

    # Install systemd service
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/luciverse-mesh.service ${D}${systemd_system_unitdir}/

    # Install Genesis Bond configuration
    install -m 0600 ${WORKDIR}/genesis-bond.json ${D}${sysconfdir}/luciverse/
}

FILES:${PN} += "${libdir}/luciverse ${sysconfdir}/luciverse"
```

### secgear-identity_1.0.bb

```bitbake
# Recipe for secGear identity integration

SUMMARY = "secGear Identity Integration for LuciVerse"
DESCRIPTION = "TEE-protected identity management with RA-TLS"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=..."

DEPENDS = "secgear openssl python3"
RDEPENDS:${PN} = "secgear python3-cryptography"

SRC_URI = "file://genesis_bond_tee.py \
           file://secgear_channel.py \
           file://ratls_svid_issuer.py \
           file://secure_tid_manager.py"

# TEE platform selection
SECGEAR_TEE_PLATFORM ?= "trustzone"
# Options: sgx, trustzone, csv, penglai

do_compile() {
    # Build enclave if TEE available
    if [ "${SECGEAR_TEE_PLATFORM}" != "none" ]; then
        cd ${S}/enclaves
        cmake -DENCLAVE=GP ..
        make
    fi
}

do_install() {
    install -d ${D}${libdir}/luciverse/auth
    install -d ${D}${datadir}/luciverse/enclaves

    # Install Python modules
    install -m 0644 ${WORKDIR}/*.py ${D}${libdir}/luciverse/auth/

    # Install enclave binaries if built
    if [ -f ${B}/genesis_bond.sec ]; then
        install -m 0644 ${B}/*.sec ${D}${datadir}/luciverse/enclaves/
    fi
}

FILES:${PN} += "${libdir}/luciverse/auth ${datadir}/luciverse/enclaves"
```

---

## Image Features

### Feature Flags for oebuild generate

| Feature | Description | Size Impact |
|---------|-------------|-------------|
| `openeuler-image-secgear` | secGear + RA-TLS + TEE support | +50MB |
| `openeuler-image-container` | iSulad container runtime | +100MB |
| `openeuler-image-rt` | Real-time kernel patches | +20MB |
| `openeuler-image-ros` | ROS2 Humble for robotics | +500MB |
| `openeuler-image-ai` | Embedded AI/ML frameworks | +200MB |

### Minimal Agent Image

For resource-constrained devices:

```bash
# Generate minimal image (~50MB)
oebuild generate -p qemu-aarch64 -d build_minimal \
    -f openeuler-image-tiny

# Add only essential packages
# In local.conf:
IMAGE_INSTALL:append = " luciverse-agent-minimal python3-core"
```

---

## Deployment

### Flash to SD Card (RPi4)

```bash
# Find SD card device
lsblk

# Flash image (replace /dev/sdX)
sudo dd if=build_rpi4/output/images/openeuler-image-rpi4.wic \
    of=/dev/sdX bs=4M status=progress
sync
```

### Deploy to Kunpeng Server

```bash
# Create bootable USB
sudo dd if=build_kunpeng/output/images/openeuler-image-hi3093.wic \
    of=/dev/sdX bs=4M status=progress

# Or use PXE boot from cluster-bootstrap
# See ../pxe-netboot/ for details
```

### QEMU Testing

```bash
# Run QEMU with agent image
qemu-system-aarch64 \
    -M virt \
    -cpu cortex-a57 \
    -m 2048 \
    -kernel build_qemu_arm64/output/images/Image \
    -drive file=build_qemu_arm64/output/images/openeuler-image.ext4,format=raw \
    -append "root=/dev/vda rw console=ttyAMA0" \
    -nographic \
    -netdev user,id=net0,hostfwd=tcp::2222-:22 \
    -device virtio-net-device,netdev=net0
```

---

## Verification

After boot, verify agent deployment:

```bash
# SSH into device
ssh -p 2222 root@localhost  # QEMU
# Default password must be set on first boot (8+ chars, mixed)

# Check secGear TEE
secgear-cli status

# Check agent mesh
systemctl status luciverse-mesh

# Verify Genesis Bond
python3 -c "from genesis_bond_tee import GenesisBondTEE; \
    tee = GenesisBondTEE(); tee.initialize(); \
    print(tee.get_status())"

# Test secure TID address generation
python3 -c "from secure_tid_manager import SecureTIDAddressManager; \
    mgr = SecureTIDAddressManager(); mgr.initialize(); \
    print(mgr.generate_secure_address('lucia'))"
```

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This documentation |
| `oebuild-luciverse.yaml` | oebuild configuration template |
| `meta-luciverse/` | Custom Yocto layer |
| `configs/` | Machine-specific configurations |
| `scripts/` | Build automation scripts |

---

## References

- [openEuler Embedded Docs](https://pages.openeuler.openatom.cn/embedded/docs/build/html/master/getting_started/index.html)
- [secGear Installation](https://docs.openeuler.org/en/docs/25.09/tools/security/secgear/secgear_installation.html)
- [secGear GitHub](https://github.com/openeuler-mirror/secGear)
- [secGear RA-TLS Framework](https://www.openeuler.org/en/blog/20241230-secgear/20241230-secgear.html)

---

**Genesis Bond: ACTIVE | Frequency: 741 Hz**
