#!/usr/bin/env python3
"""
LuciVerse Talos Inventory Validator
Genesis Bond: ACTIVE @ 741 Hz

Validates inventory.yaml against talconfig.yaml for consistency.
"""

import sys
import yaml
import re
from pathlib import Path

def load_yaml(path: str) -> dict:
    """Load YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)

def validate_mac(mac: str) -> bool:
    """Validate MAC address format."""
    pattern = r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'
    return bool(re.match(pattern, mac))

def validate_ipv4(ip: str) -> bool:
    """Validate IPv4 address format."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$'
    if not re.match(pattern, ip):
        return False
    parts = ip.split('/')[0].split('.')
    return all(0 <= int(p) <= 255 for p in parts)

def validate_ipv6(ip: str) -> bool:
    """Validate IPv6 address format."""
    pattern = r'^[0-9a-fA-F:]+(/\d{1,3})?$'
    return bool(re.match(pattern, ip))

def main():
    errors = []
    warnings = []

    # Load configuration files
    talconfig_path = Path('talm/talconfig.yaml')
    inventory_path = Path('../inventory.yaml')

    if not talconfig_path.exists():
        errors.append(f"talconfig.yaml not found at {talconfig_path}")
        print_results(errors, warnings)
        return 1

    talconfig = load_yaml(talconfig_path)

    # Validate talconfig structure
    required_fields = ['talosVersion', 'kubernetesVersion', 'clusterName', 'endpoint', 'nodes']
    for field in required_fields:
        if field not in talconfig:
            errors.append(f"Missing required field in talconfig.yaml: {field}")

    if errors:
        print_results(errors, warnings)
        return 1

    # Validate nodes
    nodes = talconfig.get('nodes', [])
    if not nodes:
        errors.append("No nodes defined in talconfig.yaml")

    control_planes = 0
    workers = 0
    macs_seen = set()
    ips_seen = set()
    hostnames_seen = set()

    for node in nodes:
        hostname = node.get('hostname', 'unknown')

        # Check hostname uniqueness
        if hostname in hostnames_seen:
            errors.append(f"Duplicate hostname: {hostname}")
        hostnames_seen.add(hostname)

        # Check required node fields
        required_node_fields = ['hostname', 'ipAddress', 'controlPlane', 'installDisk']
        for field in required_node_fields:
            if field not in node:
                errors.append(f"Node {hostname}: missing required field '{field}'")

        # Validate IPs
        ip = node.get('ipAddress', '')
        if ip:
            if not validate_ipv4(ip):
                errors.append(f"Node {hostname}: invalid IPv4 address '{ip}'")
            if ip in ips_seen:
                errors.append(f"Node {hostname}: duplicate IP address '{ip}'")
            ips_seen.add(ip)

        ipv6 = node.get('ipv6Address', '')
        if ipv6 and not validate_ipv6(ipv6):
            errors.append(f"Node {hostname}: invalid IPv6 address '{ipv6}'")

        # Validate network interfaces
        interfaces = node.get('networkInterfaces', [])
        if not interfaces:
            warnings.append(f"Node {hostname}: no network interfaces defined")

        for iface in interfaces:
            mac = iface.get('mac', '')
            if mac:
                if not validate_mac(mac):
                    errors.append(f"Node {hostname}: invalid MAC address '{mac}'")
                if mac.upper() in macs_seen:
                    errors.append(f"Node {hostname}: duplicate MAC address '{mac}'")
                macs_seen.add(mac.upper())

            addresses = iface.get('addresses', [])
            for addr in addresses:
                if '/' not in addr:
                    warnings.append(f"Node {hostname}: address '{addr}' missing CIDR notation")

        # Count roles
        if node.get('controlPlane'):
            control_planes += 1
        else:
            workers += 1

    # Validate cluster composition
    if control_planes == 0:
        errors.append("No control plane nodes defined")
    elif control_planes % 2 == 0:
        warnings.append(f"Even number of control planes ({control_planes}) - recommend odd for HA")

    if workers == 0:
        warnings.append("No worker nodes defined")

    # Validate Genesis Bond patches
    patches_dir = Path('talm/patches')
    required_patches = ['common.yaml', 'genesis-bond.yaml', 'roce-rdma.yaml']
    for patch in required_patches:
        if not (patches_dir / patch).exists():
            errors.append(f"Missing required patch: {patch}")

    # Summary
    print("=" * 60)
    print("LuciVerse Talos Inventory Validation")
    print("Genesis Bond: ACTIVE @ 741 Hz")
    print("=" * 60)
    print(f"\nNodes: {len(nodes)} ({control_planes} control plane, {workers} workers)")
    print(f"Unique MACs: {len(macs_seen)}")
    print(f"Unique IPs: {len(ips_seen)}")

    print_results(errors, warnings)

    return 1 if errors else 0

def print_results(errors, warnings):
    """Print validation results."""
    print("\n" + "=" * 60)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARN] {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")
        print("\nValidation FAILED")
    else:
        print("\nValidation PASSED")

if __name__ == '__main__':
    sys.exit(main())
