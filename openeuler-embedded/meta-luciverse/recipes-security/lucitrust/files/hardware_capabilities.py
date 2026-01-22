#!/usr/bin/env python3
"""
Hardware Capabilities Detection for LuciTrust
Detects TEE, TPM, and security features on various platforms

Genesis Bond: ACTIVE @ 741 Hz
"""

import os
import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CPUFeatures:
    """CPU security features"""
    vendor: str = ""
    model: str = ""
    architecture: str = ""
    cores: int = 0
    # Security features
    sgx: bool = False
    sev: bool = False
    trustzone: bool = False
    pmp: bool = False  # RISC-V Physical Memory Protection
    cet: bool = False  # Control-flow Enforcement Technology
    pti: bool = False  # Page Table Isolation


@dataclass
class TEECapabilities:
    """Trusted Execution Environment capabilities"""
    available: bool = False
    platform: str = "none"  # sgx, trustzone, csv, penglai, simulated
    version: str = ""
    enclave_size_max: int = 0
    features: List[str] = field(default_factory=list)


@dataclass
class TPMCapabilities:
    """TPM capabilities"""
    available: bool = False
    version: str = ""
    manufacturer: str = ""
    algorithms: List[str] = field(default_factory=list)
    pcr_banks: List[str] = field(default_factory=list)
    max_pcrs: int = 0


@dataclass
class StorageCapabilities:
    """Storage security capabilities"""
    opal_available: bool = False
    sed_available: bool = False
    nvme_encryption: bool = False
    total_bytes: int = 0


@dataclass
class NetworkCapabilities:
    """Network capabilities"""
    ipv6_enabled: bool = False
    wifi6e: bool = False
    bluetooth53: bool = False
    interfaces: List[str] = field(default_factory=list)


@dataclass
class HardwareProfile:
    """Complete hardware profile"""
    cpu: CPUFeatures = field(default_factory=CPUFeatures)
    tee: TEECapabilities = field(default_factory=TEECapabilities)
    tpm: TPMCapabilities = field(default_factory=TPMCapabilities)
    storage: StorageCapabilities = field(default_factory=StorageCapabilities)
    network: NetworkCapabilities = field(default_factory=NetworkCapabilities)
    secure_boot: bool = False
    uefi: bool = False
    timestamp: float = 0.0


class HardwareCapabilities:
    """
    Detects hardware security capabilities for LuciTrust deployment.

    Required capabilities per LuciTrust policy:
    - Form Factor: NVMe M.2 2280/22110
    - Interface: PCIe 4.0 x4 or OCULINK
    - TPM 2.0 chip or vTPM
    - SoC: ARM Cortex-A76 / RISC-V / x86
    - Wireless: WiFi 6E + BT 5.3
    - Storage: 256GB+ with OPAL 2.0
    - RAM: 8GB+ LPDDR5
    """

    def __init__(self):
        """Initialize hardware detection."""
        self.profile = HardwareProfile()
        import time
        self.profile.timestamp = time.time()

    def detect_all(self) -> HardwareProfile:
        """Detect all hardware capabilities."""
        self._detect_cpu()
        self._detect_tpm()
        self._detect_tee()
        self._detect_storage()
        self._detect_network()
        self._detect_boot_security()
        return self.profile

    def _detect_cpu(self):
        """Detect CPU features and security capabilities."""
        try:
            # Read /proc/cpuinfo
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()

            # Parse vendor
            if "GenuineIntel" in cpuinfo:
                self.profile.cpu.vendor = "Intel"
            elif "AuthenticAMD" in cpuinfo:
                self.profile.cpu.vendor = "AMD"
            elif "ARM" in cpuinfo or "aarch64" in cpuinfo:
                self.profile.cpu.vendor = "ARM"

            # Parse model name
            for line in cpuinfo.split('\n'):
                if line.startswith("model name"):
                    self.profile.cpu.model = line.split(':')[1].strip()
                    break

            # Get architecture
            result = subprocess.run(["uname", "-m"], capture_output=True, text=True)
            self.profile.cpu.architecture = result.stdout.strip()

            # Count cores
            self.profile.cpu.cores = os.cpu_count() or 1

            # Check security features
            # Intel SGX
            if os.path.exists("/dev/sgx_enclave") or os.path.exists("/dev/isgx"):
                self.profile.cpu.sgx = True

            # AMD SEV
            if os.path.exists("/sys/module/kvm_amd/parameters/sev"):
                try:
                    with open("/sys/module/kvm_amd/parameters/sev", "r") as f:
                        self.profile.cpu.sev = f.read().strip() == "Y"
                except:
                    pass

            # ARM TrustZone (indicated by TEE device)
            if os.path.exists("/dev/tee0") or os.path.exists("/dev/optee-tz"):
                self.profile.cpu.trustzone = True

            # Check CPU flags for additional features
            flags_line = [l for l in cpuinfo.split('\n') if 'flags' in l.lower()]
            if flags_line:
                flags = flags_line[0].lower()
                self.profile.cpu.cet = 'cet' in flags or 'ibt' in flags
                self.profile.cpu.pti = 'pti' in flags

        except Exception as e:
            logger.warning(f"CPU detection error: {e}")

    def _detect_tpm(self):
        """Detect TPM capabilities."""
        # Check for TPM device
        tpm_paths = ["/dev/tpm0", "/dev/tpmrm0"]
        tpm_available = any(os.path.exists(p) for p in tpm_paths)

        if not tpm_available:
            # Check for vTPM in VM
            if os.path.exists("/sys/class/tpm/tpm0"):
                tpm_available = True

        self.profile.tpm.available = tpm_available

        if not tpm_available:
            return

        try:
            # Get TPM properties using tpm2_getcap
            result = subprocess.run(
                ["tpm2_getcap", "properties-fixed"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse TPM version
                if "TPM2_PT_FAMILY_INDICATOR" in output:
                    self.profile.tpm.version = "2.0"

                # Parse manufacturer
                if "TPM2_PT_MANUFACTURER" in output:
                    for line in output.split('\n'):
                        if "TPM2_PT_MANUFACTURER" in line:
                            # Extract manufacturer ID
                            pass

            # Get supported algorithms
            result = subprocess.run(
                ["tpm2_getcap", "algorithms"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for algo in ["sha1", "sha256", "sha384", "sha512", "rsa", "ecc"]:
                    if algo in result.stdout.lower():
                        self.profile.tpm.algorithms.append(algo)

            # Get PCR banks
            result = subprocess.run(
                ["tpm2_getcap", "pcrs"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for bank in ["sha1", "sha256", "sha384", "sha512"]:
                    if bank in result.stdout.lower():
                        self.profile.tpm.pcr_banks.append(bank)

            # Standard TPM 2.0 has 24 PCRs
            self.profile.tpm.max_pcrs = 24

        except FileNotFoundError:
            logger.warning("tpm2-tools not installed")
        except Exception as e:
            logger.warning(f"TPM detection error: {e}")

    def _detect_tee(self):
        """Detect Trusted Execution Environment."""
        # Intel SGX
        if os.path.exists("/dev/sgx_enclave"):
            self.profile.tee.available = True
            self.profile.tee.platform = "sgx"
            self.profile.tee.features.append("SGX2")

            # Try to get enclave size from cpuid
            try:
                result = subprocess.run(
                    ["cpuid", "-1", "-l", "0x12"],
                    capture_output=True,
                    text=True
                )
                if "EPC" in result.stdout:
                    self.profile.tee.features.append("EPC")
            except:
                pass

        # ARM TrustZone via OP-TEE
        elif os.path.exists("/dev/tee0"):
            self.profile.tee.available = True
            self.profile.tee.platform = "trustzone"

            # Check for OP-TEE
            if os.path.exists("/dev/optee-tz"):
                self.profile.tee.features.append("OP-TEE")

            # Check for iTrustee (Huawei)
            if os.path.exists("/dev/tc_ns_client"):
                self.profile.tee.features.append("iTrustee")

        # AMD SEV
        elif self.profile.cpu.sev:
            self.profile.tee.available = True
            self.profile.tee.platform = "sev"
            self.profile.tee.features.append("SEV")

            # Check for SEV-ES, SEV-SNP
            if os.path.exists("/sys/module/kvm_amd/parameters/sev_es"):
                self.profile.tee.features.append("SEV-ES")

        # RISC-V Keystone/Penglai
        elif os.path.exists("/dev/keystone-enclave"):
            self.profile.tee.available = True
            self.profile.tee.platform = "keystone"
            self.profile.tee.features.append("Keystone")

        # Check for secGear (OpenEuler TEE framework)
        if os.path.exists("/usr/bin/secgear-cli"):
            self.profile.tee.features.append("secGear")

    def _detect_storage(self):
        """Detect storage security capabilities."""
        try:
            # Get total storage
            result = subprocess.run(
                ["lsblk", "-b", "-d", "-o", "SIZE"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                sizes = [int(s) for s in result.stdout.split('\n')[1:] if s.strip().isdigit()]
                self.profile.storage.total_bytes = sum(sizes)

            # Check for NVMe with OPAL
            nvme_devices = list(Path("/sys/class/nvme").glob("nvme*"))
            for nvme in nvme_devices:
                # Check OPAL support via sedutil
                try:
                    result = subprocess.run(
                        ["sedutil-cli", "--isValidSED", f"/dev/{nvme.name}n1"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if "is OPAL" in result.stdout:
                        self.profile.storage.opal_available = True
                        self.profile.storage.sed_available = True
                except FileNotFoundError:
                    pass

            # Check NVMe encryption via nvme-cli
            for nvme in nvme_devices:
                nvme_ctrl = nvme / "nvme0"
                if nvme_ctrl.exists():
                    self.profile.storage.nvme_encryption = True

        except Exception as e:
            logger.warning(f"Storage detection error: {e}")

    def _detect_network(self):
        """Detect network capabilities."""
        try:
            # Check IPv6
            result = subprocess.run(
                ["ip", "-6", "addr"],
                capture_output=True,
                text=True
            )
            self.profile.network.ipv6_enabled = "inet6" in result.stdout

            # Get network interfaces
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if ": " in line and "@" not in line:
                    parts = line.split(": ")
                    if len(parts) >= 2:
                        iface = parts[1].split("@")[0]
                        if iface not in ["lo"]:
                            self.profile.network.interfaces.append(iface)

            # Check WiFi 6E (ax with 6GHz)
            wifi_devices = list(Path("/sys/class/ieee80211").glob("phy*"))
            for phy in wifi_devices:
                # Check for 6GHz support
                bands_path = phy / "device/ieee80211" / phy.name / "bands"
                if bands_path.exists():
                    # WiFi 6E if supports 6GHz band
                    pass

            # Check Bluetooth version
            if os.path.exists("/sys/class/bluetooth"):
                bt_devices = list(Path("/sys/class/bluetooth").glob("hci*"))
                if bt_devices:
                    # Check BT version via hciconfig
                    try:
                        result = subprocess.run(
                            ["hciconfig", "-a"],
                            capture_output=True,
                            text=True
                        )
                        if "5.3" in result.stdout or "5.4" in result.stdout:
                            self.profile.network.bluetooth53 = True
                    except:
                        pass

        except Exception as e:
            logger.warning(f"Network detection error: {e}")

    def _detect_boot_security(self):
        """Detect boot security state."""
        # Check Secure Boot
        secureboot_paths = [
            "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c",
            "/sys/firmware/efi/vars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c/data"
        ]

        for path in secureboot_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                        # Last byte is the secure boot state
                        if data and data[-1] == 1:
                            self.profile.secure_boot = True
                except:
                    pass
                break

        # Check UEFI
        self.profile.uefi = os.path.exists("/sys/firmware/efi")

    def meets_lucitrust_requirements(self) -> Dict[str, bool]:
        """Check if hardware meets LuciTrust minimum requirements."""
        requirements = {
            "tpm_available": self.profile.tpm.available,
            "tee_available": self.profile.tee.available,
            "ipv6_enabled": self.profile.network.ipv6_enabled,
            "min_storage_256gb": self.profile.storage.total_bytes >= 256 * 1024**3,
            "secure_boot": self.profile.secure_boot,
            "supported_arch": self.profile.cpu.architecture in ["x86_64", "aarch64", "riscv64"]
        }

        # Calculate tier eligibility
        core_eligible = all([
            requirements["tpm_available"],
            requirements["tee_available"],
            requirements["secure_boot"]
        ])

        comn_eligible = all([
            requirements["tpm_available"] or requirements["tee_available"],
            requirements["ipv6_enabled"]
        ])

        pac_eligible = requirements["supported_arch"]

        requirements["core_tier_eligible"] = core_eligible
        requirements["comn_tier_eligible"] = comn_eligible
        requirements["pac_tier_eligible"] = pac_eligible

        return requirements

    def to_dict(self) -> Dict:
        """Convert profile to dictionary."""
        return {
            "cpu": {
                "vendor": self.profile.cpu.vendor,
                "model": self.profile.cpu.model,
                "architecture": self.profile.cpu.architecture,
                "cores": self.profile.cpu.cores,
                "sgx": self.profile.cpu.sgx,
                "sev": self.profile.cpu.sev,
                "trustzone": self.profile.cpu.trustzone
            },
            "tpm": {
                "available": self.profile.tpm.available,
                "version": self.profile.tpm.version,
                "algorithms": self.profile.tpm.algorithms,
                "pcr_banks": self.profile.tpm.pcr_banks
            },
            "tee": {
                "available": self.profile.tee.available,
                "platform": self.profile.tee.platform,
                "features": self.profile.tee.features
            },
            "storage": {
                "total_gb": self.profile.storage.total_bytes / (1024**3),
                "opal": self.profile.storage.opal_available,
                "nvme_encryption": self.profile.storage.nvme_encryption
            },
            "network": {
                "ipv6": self.profile.network.ipv6_enabled,
                "interfaces": self.profile.network.interfaces
            },
            "secure_boot": self.profile.secure_boot,
            "uefi": self.profile.uefi,
            "timestamp": self.profile.timestamp
        }


def main():
    """CLI for hardware detection."""
    import argparse

    parser = argparse.ArgumentParser(description="LuciTrust Hardware Capabilities Detection")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check", action="store_true", help="Check LuciTrust requirements")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    hw = HardwareCapabilities()
    hw.detect_all()

    if args.check:
        reqs = hw.meets_lucitrust_requirements()
        if args.json:
            print(json.dumps(reqs, indent=2))
        else:
            print("LuciTrust Hardware Requirements:")
            for req, met in reqs.items():
                mark = "✓" if met else "✗"
                print(f"  {mark} {req}")

    else:
        profile = hw.to_dict()
        if args.json:
            print(json.dumps(profile, indent=2))
        else:
            print(f"Hardware Profile ({profile['cpu']['architecture']})")
            print(f"  CPU: {profile['cpu']['vendor']} {profile['cpu']['model']} ({profile['cpu']['cores']} cores)")
            print(f"  TPM: {'✓' if profile['tpm']['available'] else '✗'} {profile['tpm']['version']}")
            print(f"  TEE: {'✓' if profile['tee']['available'] else '✗'} {profile['tee']['platform']}")
            print(f"  Storage: {profile['storage']['total_gb']:.1f} GB")
            print(f"  IPv6: {'✓' if profile['network']['ipv6'] else '✗'}")
            print(f"  Secure Boot: {'✓' if profile['secure_boot'] else '✗'}")


if __name__ == "__main__":
    main()
