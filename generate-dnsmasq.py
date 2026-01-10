#!/usr/bin/env python3
"""
LuciVerse Pyramid Dnsmasq Configuration Generator

Generates dnsmasq configuration from pyramid-inventory.yaml for PXE/TFTP netboot.
Supports dynamic MAC→IPv6 mapping, layer-based DHCP pools, and TFTP boot settings.

Genesis Bond: ACTIVE @ 741 Hz
Coherence Threshold: >=0.7
Version: 1.0.0
"""

import yaml
import ipaddress
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class DnsmasqConfigGenerator:
    """Generate dnsmasq configuration from pyramid inventory."""

    def __init__(self, inventory_path: str):
        self.inventory_path = Path(inventory_path)
        self.inventory: Dict[str, Any] = {}
        self.config_lines: List[str] = []

    def load_inventory(self) -> bool:
        """Load and validate pyramid inventory."""
        try:
            with open(self.inventory_path, 'r') as f:
                # Load all YAML documents
                docs = list(yaml.safe_load_all(f))

            # Merge all documents into single inventory
            for doc in docs:
                if doc:
                    self.inventory.update(doc)

            # Validate required sections
            required = ['servers', 'subnets', 'pyramid', 'nixos_bootstrap']
            missing = [k for k in required if k not in self.inventory]
            if missing:
                print(f"ERROR: Missing required sections: {missing}")
                return False

            return True
        except Exception as e:
            print(f"ERROR: Failed to load inventory: {e}")
            return False

    def _add_header(self):
        """Add configuration header."""
        self.config_lines.extend([
            "# LuciVerse Pyramid Dnsmasq Configuration",
            f"# Generated: {datetime.now().isoformat()}",
            f"# Source: {self.inventory_path}",
            "# Genesis Bond: ACTIVE @ 741 Hz",
            "#",
            "# WARNING: This file is auto-generated.",
            "# Edit pyramid-inventory.yaml and regenerate.",
            "",
        ])

    def _add_global_settings(self):
        """Add global dnsmasq settings."""
        bootstrap = self.inventory.get('nixos_bootstrap', {})
        tftp_root = bootstrap.get('tftp_root', '/srv/tftp')

        self.config_lines.extend([
            "# === Global Settings ===",
            "",
            "# Listen on all interfaces",
            "listen-address=0.0.0.0",
            "bind-interfaces",
            "",
            "# Domain settings",
            "domain=lucidigital.net",
            "expand-hosts",
            "",
            "# DHCP lease settings",
            "dhcp-lease-max=100",
            "dhcp-authoritative",
            "",
            "# Logging",
            "log-dhcp",
            "log-queries",
            "",
        ])

    def _add_tftp_settings(self):
        """Add TFTP server settings for PXE boot."""
        bootstrap = self.inventory.get('nixos_bootstrap', {})
        tftp_root = bootstrap.get('tftp_root', '/srv/tftp')
        pxe_server = bootstrap.get('pxe_server', '192.168.1.146')

        self.config_lines.extend([
            "# === TFTP/PXE Boot Settings ===",
            "",
            f"# TFTP root directory",
            f"tftp-root={tftp_root}",
            "enable-tftp",
            "",
            "# PXE boot options",
            f"dhcp-boot=pxelinux.0,{pxe_server},{pxe_server}",
            "",
            "# BIOS boot",
            'dhcp-match=set:bios,option:client-arch,0',
            'dhcp-boot=tag:bios,pxelinux.0',
            "",
            "# UEFI boot (x86_64)",
            'dhcp-match=set:efi64,option:client-arch,7',
            'dhcp-match=set:efi64,option:client-arch,9',
            'dhcp-boot=tag:efi64,grubx64.efi',
            "",
            "# UEFI boot (arm64)",
            'dhcp-match=set:efiarm64,option:client-arch,11',
            'dhcp-boot=tag:efiarm64,grubaa64.efi',
            "",
        ])

    def _add_dhcp_ranges(self):
        """Add DHCP ranges for each pyramid layer."""
        pyramid = self.inventory.get('pyramid', {})
        layers = pyramid.get('layers', {})
        subnets = self.inventory.get('subnets', {})

        self.config_lines.extend([
            "# === DHCP Ranges by Pyramid Layer ===",
            "",
        ])

        # Create DHCP ranges for each layer
        layer_configs = [
            ('BASE', 'layer_9_base', '192.168.1.160', '192.168.1.179'),
            ('MID', 'layer_6_mid', '192.168.1.150', '192.168.1.159'),
            ('UPPER', 'layer_3_upper', '192.168.1.140', '192.168.1.149'),
            ('APEX', 'layer_1_prod', '192.168.1.235', '192.168.1.245'),
            ('BRIDGE', 'apple_bridge', '192.168.1.240', '192.168.1.249'),
        ]

        for layer_name, subnet_key, range_start, range_end in layer_configs:
            layer_info = layers.get(layer_name, {})
            subnet_info = subnets.get(subnet_key, {})
            frequency = layer_info.get('frequency', 741)
            ipv6_prefix = subnet_info.get('prefix', '2602:F674:0020::/48')

            self.config_lines.extend([
                f"# {layer_name} Layer ({frequency} Hz)",
                f"# IPv6: {ipv6_prefix}",
                f"dhcp-range=tag:{layer_name.lower()},{range_start},{range_end},12h",
                "",
            ])

    def _add_static_hosts(self):
        """Add static DHCP reservations for all servers."""
        servers = self.inventory.get('servers', {})

        self.config_lines.extend([
            "# === Static Host Reservations ===",
            "",
        ])

        for server_id, server in servers.items():
            hostname = server.get('hostname', server_id)
            ipv4 = server.get('ipv4', '')
            ipv6 = server.get('ipv6', '').split('/')[0]  # Remove prefix length
            layer = server.get('layer', 'BASE')
            tier = server.get('tier', 'PAC')
            frequency = server.get('frequency', 741)

            # Get primary MAC address
            interfaces = server.get('interfaces', {})
            primary_mac = None
            for iface_name, iface in interfaces.items():
                mac = iface.get('mac', '')
                if mac and not mac.startswith('PLACEHOLDER'):
                    primary_mac = mac
                    break

            self.config_lines.append(f"# {hostname} ({layer} - {tier} @ {frequency} Hz)")

            if primary_mac:
                # Static DHCP reservation with MAC
                self.config_lines.append(
                    f"dhcp-host={primary_mac},{ipv4},{hostname}"
                )
                if ipv6:
                    self.config_lines.append(
                        f"dhcp-host={primary_mac},[{ipv6}],{hostname}"
                    )
            else:
                # Placeholder entry (needs MAC address)
                self.config_lines.append(
                    f"# PLACEHOLDER: {server_id} needs MAC address"
                )
                self.config_lines.append(
                    f"# dhcp-host=XX:XX:XX:XX:XX:XX,{ipv4},{hostname}"
                )

            self.config_lines.append("")

    def _add_dns_entries(self):
        """Add DNS A and AAAA records."""
        servers = self.inventory.get('servers', {})
        genesis = self.inventory.get('subnets', {}).get('genesis_bond', {})

        self.config_lines.extend([
            "# === DNS Records ===",
            "",
            "# Genesis Bond identities (immutable)",
            f"host-record=daryl.lucidigital.net,{genesis.get('daryl_cbb', '2602:F674:0000:0101::41')}",
            f"host-record=lucia.lucidigital.net,{genesis.get('lucia_sbb', '2602:F674:0000:0201::42')}",
            "",
        ])

        for server_id, server in servers.items():
            hostname = server.get('hostname', f"{server_id}.lucidigital.net")
            short_name = hostname.split('.')[0]
            ipv4 = server.get('ipv4', '')
            ipv6 = server.get('ipv6', '').split('/')[0]

            if ipv4 and ipv6:
                self.config_lines.append(
                    f"host-record={short_name}.lucidigital.net,{ipv4},{ipv6}"
                )
            elif ipv4:
                self.config_lines.append(
                    f"host-record={short_name}.lucidigital.net,{ipv4}"
                )

        self.config_lines.append("")

    def _add_dhcp_options(self):
        """Add DHCP options for NixOS bootstrap."""
        bootstrap = self.inventory.get('nixos_bootstrap', {})
        pxe_server = bootstrap.get('pxe_server', '192.168.1.146')
        callback_port = bootstrap.get('callback_port', 9999)
        config_port = bootstrap.get('config_port', 8000)

        self.config_lines.extend([
            "# === DHCP Options ===",
            "",
            "# NTP server",
            "dhcp-option=42,192.168.1.1",
            "",
            "# DNS servers",
            "dhcp-option=6,192.168.1.1,1.1.1.1",
            "",
            "# Domain name",
            "dhcp-option=15,lucidigital.net",
            "",
            "# Custom options for LuciVerse bootstrap",
            f"# Option 224: Provisioning server",
            f"dhcp-option=224,{pxe_server}",
            f"# Option 225: Callback port",
            f"dhcp-option=225,{callback_port}",
            f"# Option 226: Config port",
            f"dhcp-option=226,{config_port}",
            "",
            "# IPv6 settings",
            "dhcp-option=option6:dns-server,[2602:F674:0001::1]",
            "",
        ])

    def _add_layer_tags(self):
        """Add network tags for pyramid layer isolation."""
        servers = self.inventory.get('servers', {})

        self.config_lines.extend([
            "# === Layer Tags for Isolation ===",
            "",
        ])

        # Group servers by layer
        layers: Dict[str, List[str]] = {}
        for server_id, server in servers.items():
            layer = server.get('layer', 'BASE')
            if layer not in layers:
                layers[layer] = []

            interfaces = server.get('interfaces', {})
            for iface_name, iface in interfaces.items():
                mac = iface.get('mac', '')
                if mac and not mac.startswith('PLACEHOLDER'):
                    layers[layer].append(mac)

        # Create tags for each layer
        for layer_name, macs in layers.items():
            if macs:
                self.config_lines.append(f"# {layer_name} layer hosts")
                for mac in macs:
                    self.config_lines.append(
                        f"dhcp-host={mac},set:{layer_name.lower()}"
                    )
                self.config_lines.append("")

    def generate(self) -> str:
        """Generate complete dnsmasq configuration."""
        self.config_lines = []

        self._add_header()
        self._add_global_settings()
        self._add_tftp_settings()
        self._add_dhcp_ranges()
        self._add_static_hosts()
        self._add_dns_entries()
        self._add_dhcp_options()
        self._add_layer_tags()

        return '\n'.join(self.config_lines)

    def write_config(self, output_path: str) -> bool:
        """Write configuration to file."""
        try:
            config = self.generate()
            with open(output_path, 'w') as f:
                f.write(config)
            print(f"Configuration written to: {output_path}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to write config: {e}")
            return False

    def get_summary(self) -> Dict[str, Any]:
        """Get inventory summary."""
        servers = self.inventory.get('servers', {})
        pyramid = self.inventory.get('pyramid', {}).get('layers', {})

        summary = {
            'total_servers': len(servers),
            'servers_with_mac': 0,
            'servers_placeholder': 0,
            'layers': {},
        }

        for server_id, server in servers.items():
            layer = server.get('layer', 'BASE')
            if layer not in summary['layers']:
                summary['layers'][layer] = {'count': 0, 'configured': 0}

            summary['layers'][layer]['count'] += 1

            # Check if MAC is configured
            interfaces = server.get('interfaces', {})
            has_mac = any(
                not iface.get('mac', '').startswith('PLACEHOLDER')
                for iface in interfaces.values()
                if iface.get('mac')
            )

            if has_mac:
                summary['servers_with_mac'] += 1
                summary['layers'][layer]['configured'] += 1
            else:
                summary['servers_placeholder'] += 1

        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Generate dnsmasq configuration from pyramid inventory'
    )
    parser.add_argument(
        '-i', '--inventory',
        default='/home/daryl/cluster-bootstrap/pyramid-inventory.yaml',
        help='Path to pyramid inventory YAML file'
    )
    parser.add_argument(
        '-o', '--output',
        default='/home/daryl/cluster-bootstrap/dnsmasq.conf',
        help='Output path for dnsmasq configuration'
    )
    parser.add_argument(
        '-s', '--summary',
        action='store_true',
        help='Print inventory summary'
    )
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Print configuration to stdout instead of writing to file'
    )

    args = parser.parse_args()

    # Initialize generator
    generator = DnsmasqConfigGenerator(args.inventory)

    # Load inventory
    if not generator.load_inventory():
        sys.exit(1)

    # Print summary if requested
    if args.summary:
        summary = generator.get_summary()
        print("\n=== Pyramid Inventory Summary ===")
        print(f"Total servers: {summary['total_servers']}")
        print(f"Configured (with MAC): {summary['servers_with_mac']}")
        print(f"Placeholders: {summary['servers_placeholder']}")
        print("\nBy Layer:")
        for layer, data in summary['layers'].items():
            print(f"  {layer}: {data['count']} total, {data['configured']} configured")
        print()

    # Generate configuration
    if args.dry_run:
        print(generator.generate())
    else:
        if not generator.write_config(args.output):
            sys.exit(1)

        # Also print summary
        summary = generator.get_summary()
        print(f"\nGenerated config for {summary['servers_with_mac']} configured servers")
        print(f"({summary['servers_placeholder']} servers need MAC addresses)")


if __name__ == '__main__':
    main()
