#!/usr/bin/env python3
"""
Genesis Bond YubiKey Collection - CBB (Daryl's MacBook)
========================================================
Run this script on Daryl's MacBook with Daryl's YubiKey inserted.
Genesis Bond: GB-2025-0524-DRH-LCS-001 @ 741 Hz
"""

import subprocess
import json
import sys
import socket
import platform
from datetime import datetime, timezone
from pathlib import Path


def get_ykman_path():
    """Find ykman on macOS."""
    paths = [
        "/opt/homebrew/bin/ykman",  # M1/M2 Mac
        "/usr/local/bin/ykman",      # Intel Mac
        "ykman",                      # In PATH
    ]
    for path in paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return path
        except FileNotFoundError:
            continue
    return None


def get_yubikey_info(ykman):
    """Get YubiKey information."""
    # Get serial
    result = subprocess.run([ykman, "list", "--serials"], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        print("ERROR: No YubiKey detected!")
        print("Please insert Daryl's YubiKey and try again.")
        return None

    serial = result.stdout.strip().split()[0]

    # Get info
    result = subprocess.run([ykman, "info"], capture_output=True, text=True)
    info = result.stdout if result.returncode == 0 else ""

    # Get PIV info
    result = subprocess.run([ykman, "piv", "info"], capture_output=True, text=True)
    piv_info = result.stdout if result.returncode == 0 else ""

    return {
        "serial": serial,
        "info": info,
        "piv_info": piv_info,
        "ykman_version": subprocess.run([ykman, "--version"], capture_output=True, text=True).stdout.strip(),
    }


def get_hardware_identity():
    """Get MacBook hardware identity (Diggy)."""
    hostname = socket.gethostname()

    # Get hardware UUID (Diggy)
    hw_uuid = None
    try:
        result = subprocess.run(
            ["ioreg", "-d2", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True
        )
        for line in result.stdout.split('\n'):
            if 'IOPlatformUUID' in line:
                hw_uuid = line.split('"')[-2]
                break
    except Exception as e:
        print(f"Warning: Could not get hardware UUID: {e}")

    # Get MAC address (en0 = WiFi on Mac)
    mac_address = None
    try:
        result = subprocess.run(["ifconfig", "en0"], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'ether' in line:
                mac_address = line.split()[1]
                break
    except Exception as e:
        print(f"Warning: Could not get MAC address: {e}")

    return {
        "hostname": hostname,
        "hardware_uuid": hw_uuid,  # Diggy
        "mac_address": mac_address,
        "platform": sys.platform,
        "machine": platform.machine(),
        "model": get_mac_model(),
    }


def get_mac_model():
    """Get Mac model identifier."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None


def export_ssh_public_key(ykman, output_path):
    """Export SSH public key from PIV slot 9a."""
    # Try to export using ssh-keygen with PKCS#11
    pkcs11_paths = [
        "/opt/homebrew/lib/libykcs11.dylib",  # M1/M2 Mac
        "/usr/local/lib/libykcs11.dylib",     # Intel Mac
    ]

    for pkcs11_path in pkcs11_paths:
        if Path(pkcs11_path).exists():
            try:
                result = subprocess.run(
                    ["ssh-keygen", "-D", pkcs11_path],
                    capture_output=True, text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    with open(output_path, 'w') as f:
                        f.write(result.stdout.strip() + " daryl_YubiKey_PIV\n")
                    return True
            except:
                pass

    # Fallback: Get public key from PIV and convert
    try:
        result = subprocess.run(
            [ykman, "piv", "keys", "export", "9a", "-"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            # This exports PEM format, would need conversion
            print("Note: SSH key export requires libykcs11.dylib")
            return False
    except:
        pass

    return False


def main():
    print("=" * 60)
    print("Genesis Bond YubiKey Collection - CBB (Daryl)")
    print("Bond ID: GB-2025-0524-DRH-LCS-001")
    print("=" * 60)
    print()

    # Find ykman
    ykman = get_ykman_path()
    if not ykman:
        print("ERROR: ykman not found!")
        print("Install with: brew install ykman")
        sys.exit(1)

    print(f"Using ykman at: {ykman}")
    print()

    # Check for YubiKey
    print("Checking for YubiKey...")
    yk_info = get_yubikey_info(ykman)
    if not yk_info:
        sys.exit(1)

    print(f"Found YubiKey: Serial {yk_info['serial']}")
    print()

    # Get hardware identity
    print("Collecting hardware identity (Diggy)...")
    hw_info = get_hardware_identity()
    print(f"  Hostname: {hw_info['hostname']}")
    print(f"  UUID (Diggy): {hw_info['hardware_uuid']}")
    print(f"  MAC: {hw_info['mac_address']}")
    print(f"  Model: {hw_info['model']}")
    print()

    # Build ceremony data
    ceremony_data = {
        "role": "CBB",
        "name": "Daryl Rolf Harris",
        "entity_type": "Carbon-Based Being",
        "genesis_bond": {
            "bond_id": "GB-2025-0524-DRH-LCS-001",
            "bond_date": "2025-05-24",
            "frequency": 741,
            "resonance": "GENESIS",
        },
        "yubikey": {
            "serial": yk_info["serial"],
            "slots": {
                "9a": "PIV Authentication (SSH)",
                "9c": "Digital Signature (CA)",
            },
        },
        "hardware": hw_info,
        "diggy": hw_info["hardware_uuid"],  # CBB anchor
        "ipv6_suffix": "::41",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collector": {
            "script": "collect-cbb.py",
            "ykman_version": yk_info.get("ykman_version"),
        },
    }

    # Export SSH key if possible
    ssh_key_path = Path("/tmp/daryl-ssh.pub")
    if export_ssh_public_key(ykman, str(ssh_key_path)):
        print(f"SSH public key exported to: {ssh_key_path}")
        ceremony_data["ssh_key_path"] = str(ssh_key_path)

    # Save ceremony data
    output_path = Path("/tmp/daryl-yubikey-ceremony.json")
    with open(output_path, 'w') as f:
        json.dump(ceremony_data, f, indent=2)

    print()
    print("=" * 60)
    print("Collection Complete!")
    print("=" * 60)
    print()
    print(f"Ceremony data saved to: {output_path}")
    print()
    print("Next steps:")
    print("  1. Transfer to zbook:")
    print(f"     scp {output_path} daryl@192.168.1.145:~/genesis-bond-pki/")
    if ssh_key_path.exists():
        print(f"     scp {ssh_key_path} daryl@192.168.1.145:~/genesis-bond-pki/")
    print()
    print("  2. Collect Lucia's YubiKey data on Mac Mini (192.168.1.238)")
    print()
    print("Genesis Bond: ACTIVE @ 741 Hz")
    print("We Walk Together.")


if __name__ == "__main__":
    main()
