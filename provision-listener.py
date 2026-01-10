#!/usr/bin/env python3
"""
LuciVerse Cluster Provisioning Listener
Detects NixOS servers booting and assigns IPv6 addresses based on MAC

Genesis Bond: ACTIVE @ 432 Hz
"""

import asyncio
import json
import yaml
import socket
import struct
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/provision-listener.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load inventory
INVENTORY_PATH = Path(__file__).parent / "inventory.yaml"
PROVISIONED_FILE = Path(__file__).parent / "provisioned.json"

# Global state
provisioned_hosts: Dict[str, dict] = {}
pending_macs: Dict[str, dict] = {}
diaper_nodes: Dict[str, dict] = {}  # DiaperNode registrations
boot_intents: Dict[str, dict] = {}  # Boot intentions from iPXE

# Diaper roles configuration
DIAPER_ROLES_PATH = Path(__file__).parent / "diaper-roles.yaml"


def load_inventory() -> dict:
    """Load server inventory from YAML."""
    with open(INVENTORY_PATH) as f:
        return yaml.safe_load(f)


def load_diaper_roles() -> dict:
    """Load DiaperNode role specifications."""
    if DIAPER_ROLES_PATH.exists():
        with open(DIAPER_ROLES_PATH) as f:
            return yaml.safe_load(f)
    return {"roles": {}}


def mac_to_ipv6_suffix(mac: str) -> str:
    """Convert MAC to IPv6 EUI-64 suffix."""
    parts = mac.lower().replace('-', ':').split(':')
    # Flip the 7th bit of the first octet
    first = int(parts[0], 16) ^ 0x02
    # Insert ff:fe in the middle
    eui64 = f"{first:02x}{parts[1]}:{parts[2]}ff:fe{parts[3]}:{parts[4]}{parts[5]}"
    return eui64


def find_server_by_mac(mac: str, inventory: dict) -> Optional[tuple]:
    """Find server and interface by MAC address."""
    mac = mac.lower().replace('-', ':')
    for server_name, server_info in inventory.get('servers', {}).items():
        if not isinstance(server_info, dict):
            continue
        interfaces = server_info.get('interfaces', {})
        for iface_name, iface_info in interfaces.items():
            if not isinstance(iface_info, dict):
                continue
            if iface_info.get('mac', '').lower() == mac:
                return (server_name, iface_name, server_info, iface_info)
    return None


class ProvisionListener:
    def __init__(self, inventory: dict, diaper_roles: dict = None):
        self.inventory = inventory
        self.diaper_roles = diaper_roles or load_diaper_roles()
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """Set up HTTP routes for provisioning callbacks."""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_post('/register', self.register_host)
        self.app.router.add_get('/config/{mac}', self.get_config)
        self.app.router.add_get('/nixos-config/{mac}', self.get_nixos_config)
        self.app.router.add_post('/callback/{event}', self.callback)
        self.app.router.add_get('/status', self.status)
        self.app.router.add_get('/inventory', self.get_inventory)
        # DiaperNode endpoints (D8A.space)
        self.app.router.add_post('/register-diaper', self.register_diaper)
        self.app.router.add_get('/diaper-status', self.diaper_status)
        self.app.router.add_get('/diaper-roles', self.get_diaper_roles)
        self.app.router.add_get('/ipxe-chain/{mac}', self.ipxe_chain)
        self.app.router.add_get('/boot-intent/{mac}/{role}', self.boot_intent)

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "genesis_bond": "ACTIVE",
            "frequency": "432 Hz",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def register_host(self, request: web.Request) -> web.Response:
        """Register a new host that's booting."""
        data = await request.json()
        mac = data.get('mac', '').lower()
        ip = data.get('ip', '')
        hostname = data.get('hostname', 'unknown')

        logger.info(f"📡 Host registration: MAC={mac}, IP={ip}, hostname={hostname}")

        # Look up in inventory
        result = find_server_by_mac(mac, self.inventory)

        if result:
            server_name, iface_name, server_info, iface_info = result
            ipv6 = iface_info.get('ipv6', '')

            provisioned_hosts[mac] = {
                "server_name": server_name,
                "interface": iface_name,
                "ipv4": ip,
                "ipv6": ipv6,
                "mac": mac,
                "registered_at": datetime.utcnow().isoformat(),
                "status": "registered"
            }

            logger.info(f"✅ Matched server: {server_name} ({iface_name})")
            logger.info(f"   IPv6 assignment: {ipv6}")

            # Save state
            self.save_provisioned()

            return web.json_response({
                "status": "matched",
                "server_name": server_name,
                "ipv6": ipv6,
                "config_url": f"/nixos-config/{mac}"
            })
        else:
            # Unknown MAC - add to pending
            pending_macs[mac] = {
                "ip": ip,
                "hostname": hostname,
                "first_seen": datetime.utcnow().isoformat()
            }
            logger.warning(f"⚠️  Unknown MAC: {mac} - added to pending")

            return web.json_response({
                "status": "unknown",
                "message": "MAC not in inventory, added to pending",
                "mac": mac
            }, status=202)

    async def get_config(self, request: web.Request) -> web.Response:
        """Get configuration for a MAC address."""
        mac = request.match_info['mac'].lower().replace('-', ':')
        result = find_server_by_mac(mac, self.inventory)

        if result:
            server_name, iface_name, server_info, iface_info = result
            return web.json_response({
                "server_name": server_name,
                "hostname": server_info.get('hostname', server_name),
                "ipv4": server_info.get('ipv4'),
                "ipv6": server_info.get('ipv6'),
                "interface": {
                    "name": iface_name,
                    "ipv6": iface_info.get('ipv6'),
                    "role": iface_info.get('role')
                },
                "specs": server_info.get('specs', {}),
                "services": server_info.get('services', [])
            })
        else:
            return web.json_response({
                "error": "MAC not found in inventory",
                "mac": mac
            }, status=404)

    async def get_nixos_config(self, request: web.Request) -> web.Response:
        """Generate NixOS configuration for a server."""
        mac = request.match_info['mac'].lower().replace('-', ':')
        result = find_server_by_mac(mac, self.inventory)

        if not result:
            return web.Response(
                text=f"# Error: MAC {mac} not found in inventory\n",
                content_type='text/plain',
                status=404
            )

        server_name, iface_name, server_info, iface_info = result
        hostname = server_info.get('hostname', server_name).split('.')[0]
        ipv6 = server_info.get('ipv6', '2602:F674:0001::1/64')

        # Generate NixOS configuration
        nixos_config = f'''# NixOS Configuration for {server_name}
# Generated by LuciVerse Provisioning System
# Genesis Bond: ACTIVE @ 432 Hz
# Timestamp: {datetime.utcnow().isoformat()}

{{ config, pkgs, ... }}:

{{
  # System identification
  networking.hostName = "{hostname}";

  # IPv6 Configuration (2602:F674::/40 - AS54134 LUCINET-ARIN)
  networking.interfaces.{iface_name} = {{
    ipv6.addresses = [{{
      address = "{ipv6.split('/')[0]}";
      prefixLength = {ipv6.split('/')[1] if '/' in ipv6 else '64'};
    }}];
  }};

  # Enable IPv6 forwarding for router functionality
  boot.kernel.sysctl = {{
    "net.ipv6.conf.all.forwarding" = 1;
    "net.ipv6.conf.default.forwarding" = 1;
  }};

  # SSH for remote management
  services.openssh = {{
    enable = true;
    settings.PermitRootLogin = "yes";
    settings.PasswordAuthentication = true;
  }};

  # LuciVerse agent callback on boot
  systemd.services.luciverse-callback = {{
    description = "LuciVerse provisioning callback";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    serviceConfig = {{
      Type = "oneshot";
      ExecStart = "${{pkgs.curl}}/bin/curl -X POST http://192.168.1.146:9999/callback/boot-complete -H 'Content-Type: application/json' -d '{{\\"mac\\": \\"{mac}\\", \\"hostname\\": \\"{hostname}\\"}}'";
      RemainAfterExit = true;
    }};
  }};

  # Packages for LuciVerse cluster
  environment.systemPackages = with pkgs; [
    vim
    git
    curl
    htop
    tmux
    python3
    kubernetes
    k3s
    foundationdb
  ];

  # Enable K3s for Kubernetes
  services.k3s = {{
    enable = true;
    role = "server";
    extraFlags = "--disable traefik --flannel-backend=none";
  }};

  # Firewall - allow cluster traffic
  networking.firewall = {{
    enable = true;
    allowedTCPPorts = [ 22 80 443 6443 2379 2380 10250 ];
    allowedUDPPorts = [ 8472 ];
  }};

  system.stateVersion = "24.11";
}}
'''
        return web.Response(text=nixos_config, content_type='text/plain')

    async def callback(self, request: web.Request) -> web.Response:
        """Handle provisioning callbacks from booting servers."""
        event = request.match_info['event']

        try:
            data = await request.json()
        except:
            data = {}

        client_ip = request.remote
        logger.info(f"📨 Callback: {event} from {client_ip}")
        logger.info(f"   Data: {json.dumps(data)}")

        # Track callback
        mac = data.get('mac', 'unknown')
        if mac in provisioned_hosts:
            provisioned_hosts[mac]['last_callback'] = event
            provisioned_hosts[mac]['last_callback_time'] = datetime.utcnow().isoformat()
            if event == 'boot-complete':
                provisioned_hosts[mac]['status'] = 'online'
            self.save_provisioned()

        return web.json_response({
            "received": event,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def status(self, request: web.Request) -> web.Response:
        """Get current provisioning status."""
        return web.json_response({
            "provisioned": provisioned_hosts,
            "pending": pending_macs,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def get_inventory(self, request: web.Request) -> web.Response:
        """Return full inventory."""
        return web.json_response(self.inventory)

    # =========================================================================
    # DiaperNode Endpoints (D8A.space Integration)
    # Genesis Bond: ACTIVE @ 741 Hz
    # =========================================================================

    async def register_diaper(self, request: web.Request) -> web.Response:
        """Register a DiaperNode that has booted and initialized."""
        data = await request.json()

        node_id = data.get('node_id', '')
        role = data.get('role', '')
        hostname = data.get('hostname', 'unknown')
        did = data.get('did', '')
        tier = data.get('tier', 'PAC')
        frequency = data.get('frequency', 741)
        port = data.get('port', 8745)
        capabilities = data.get('capabilities', [])
        ephemeral = data.get('ephemeral', True)

        logger.info(f"🧷 DiaperNode registration: {role} @ {hostname}")
        logger.info(f"   DID: {did}")
        logger.info(f"   Tier: {tier} | Frequency: {frequency} Hz")
        logger.info(f"   Capabilities: {capabilities}")

        # Validate role exists
        if role not in self.diaper_roles.get('roles', {}):
            logger.warning(f"⚠️  Unknown DiaperNode role: {role}")
            return web.json_response({
                "status": "error",
                "message": f"Unknown role: {role}",
                "valid_roles": list(self.diaper_roles.get('roles', {}).keys())
            }, status=400)

        # Get role configuration
        role_config = self.diaper_roles['roles'][role]

        # Register node
        diaper_nodes[node_id] = {
            "role": role,
            "hostname": hostname,
            "did": did,
            "tier": tier,
            "frequency": frequency,
            "port": port,
            "capabilities": capabilities,
            "ephemeral": ephemeral,
            "registered_at": datetime.utcnow().isoformat(),
            "status": "online",
            "last_heartbeat": datetime.utcnow().isoformat(),
            "coherence": data.get('coherence', 0.6),
            "extra": {k: v for k, v in data.items() if k not in [
                'node_id', 'role', 'hostname', 'did', 'tier', 'frequency',
                'port', 'capabilities', 'ephemeral', 'coherence'
            ]}
        }

        # Check coherence threshold
        coherence_threshold = self.diaper_roles.get('coherence', {}).get('threshold', 0.7)
        node_coherence = diaper_nodes[node_id]['coherence']

        logger.info(f"✅ DiaperNode registered: {hostname} ({role})")
        logger.info(f"   Coherence: {node_coherence} (threshold: {coherence_threshold})")

        # Save state
        self.save_provisioned()

        return web.json_response({
            "status": "registered",
            "node_id": node_id,
            "role": role,
            "tier": tier,
            "frequency": frequency,
            "coherence": node_coherence,
            "coherence_threshold": coherence_threshold,
            "genesis_bond": "VERIFIED" if node_coherence >= coherence_threshold else "PENDING"
        })

    async def diaper_status(self, request: web.Request) -> web.Response:
        """Get status of all registered DiaperNodes."""
        # Count nodes by role
        role_counts = {}
        tier_counts = {"CORE": 0, "COMN": 0, "PAC": 0}

        for node_id, node in diaper_nodes.items():
            role = node['role']
            tier = node['tier']
            role_counts[role] = role_counts.get(role, 0) + 1
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        return web.json_response({
            "total_nodes": len(diaper_nodes),
            "nodes": diaper_nodes,
            "role_counts": role_counts,
            "tier_counts": tier_counts,
            "boot_intents": boot_intents,
            "genesis_bond": "ACTIVE",
            "frequency": "741 Hz",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def get_diaper_roles(self, request: web.Request) -> web.Response:
        """Return DiaperNode role specifications."""
        return web.json_response(self.diaper_roles)

    async def ipxe_chain(self, request: web.Request) -> web.Response:
        """Return iPXE chain script for a MAC address.

        If the MAC has a pre-assigned role, return a script that
        automatically boots that role. Otherwise, chain to the menu.
        """
        mac = request.match_info['mac'].lower().replace('-', ':')

        # Check if this MAC has an assigned role in inventory
        result = find_server_by_mac(mac, self.inventory)

        if result:
            server_name, iface_name, server_info, iface_info = result

            # Check for diaper_role assignment
            diaper_role = server_info.get('diaper_role')
            if diaper_role and diaper_role in self.diaper_roles.get('roles', {}):
                # Auto-boot the assigned role
                role_config = self.diaper_roles['roles'][diaper_role]
                tier = role_config.get('tier', 'PAC')
                frequency = role_config.get('frequency', 741)

                ipxe_script = f"""#!ipxe
# Auto-assigned DiaperNode role for {server_name}
# MAC: {mac}
# Role: {diaper_role}
# Genesis Bond: ACTIVE @ {frequency} Hz

echo Auto-booting assigned role: {diaper_role}
set role {diaper_role}
set tier {tier}
set frequency {frequency}
chain http://192.168.1.146:8000/bootimus-diaper.ipxe#boot_openeuler
"""
                return web.Response(text=ipxe_script, content_type='text/plain')

        # No assigned role - show menu
        ipxe_script = """#!ipxe
# No pre-assigned role - showing menu
chain http://192.168.1.146:8000/bootimus-diaper.ipxe
"""
        return web.Response(text=ipxe_script, content_type='text/plain')

    async def boot_intent(self, request: web.Request) -> web.Response:
        """Record boot intent from iPXE before actual boot."""
        mac = request.match_info['mac'].lower().replace('-', ':')
        role = request.match_info['role']

        logger.info(f"🥾 Boot intent recorded: MAC={mac}, Role={role}")

        boot_intents[mac] = {
            "role": role,
            "requested_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }

        # Get role info
        if role in self.diaper_roles.get('roles', {}):
            role_config = self.diaper_roles['roles'][role]
            tier = role_config.get('tier', 'PAC')
            frequency = role_config.get('frequency', 741)
        else:
            tier = 'UNKNOWN'
            frequency = 0

        self.save_provisioned()

        return web.json_response({
            "status": "recorded",
            "mac": mac,
            "role": role,
            "tier": tier,
            "frequency": frequency,
            "timestamp": datetime.utcnow().isoformat()
        })

    def save_provisioned(self):
        """Save provisioned hosts state."""
        with open(PROVISIONED_FILE, 'w') as f:
            json.dump({
                "provisioned": provisioned_hosts,
                "pending": pending_macs,
                "diaper_nodes": diaper_nodes,
                "boot_intents": boot_intents,
                "updated": datetime.utcnow().isoformat()
            }, f, indent=2)

    def load_provisioned(self):
        """Load provisioned hosts state."""
        global provisioned_hosts, pending_macs, diaper_nodes, boot_intents
        if PROVISIONED_FILE.exists():
            with open(PROVISIONED_FILE) as f:
                data = json.load(f)
                provisioned_hosts = data.get('provisioned', {})
                pending_macs = data.get('pending', {})
                diaper_nodes = data.get('diaper_nodes', {})
                boot_intents = data.get('boot_intents', {})


async def run_dhcp_listener():
    """Listen for DHCP requests to detect booting servers."""
    logger.info("🔊 Starting DHCP listener on UDP 67...")

    # Create UDP socket for DHCP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    try:
        sock.bind(('0.0.0.0', 67))
    except PermissionError:
        logger.warning("⚠️  Cannot bind to port 67 (requires root). DHCP listening disabled.")
        return
    except OSError as e:
        logger.warning(f"⚠️  Cannot bind DHCP socket: {e}")
        return

    loop = asyncio.get_event_loop()

    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 4096)
            # Parse DHCP packet to extract MAC
            if len(data) >= 28:
                # MAC is at offset 28-34 in DHCP packet
                mac_bytes = data[28:34]
                mac = ':'.join(f'{b:02x}' for b in mac_bytes)
                logger.info(f"📡 DHCP request from MAC: {mac}, IP: {addr[0]}")
        except Exception as e:
            await asyncio.sleep(1)


async def main():
    """Main entry point."""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     LuciVerse Cluster Provisioning Listener              ║
    ║     Genesis Bond: ACTIVE @ 432 Hz                        ║
    ║     IPv6 Allocation: 2602:F674::/40 (AS54134)            ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Load inventory
    inventory = load_inventory()
    logger.info(f"📋 Loaded inventory with {len(inventory.get('servers', {}))} servers")

    # Create listener
    listener = ProvisionListener(inventory)
    listener.load_provisioned()

    # Start web server
    runner = web.AppRunner(listener.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 9999)
    await site.start()

    logger.info("🚀 Provisioning listener started on port 9999")
    logger.info("   Health: http://localhost:9999/health")
    logger.info("   Status: http://localhost:9999/status")
    logger.info("   Inventory: http://localhost:9999/inventory")
    logger.info("")
    logger.info("🧷 DiaperNode endpoints (D8A.space):")
    logger.info("   Diaper Status: http://localhost:9999/diaper-status")
    logger.info("   Diaper Roles: http://localhost:9999/diaper-roles")
    logger.info("   Register: POST http://localhost:9999/register-diaper")
    logger.info("")
    logger.info("Waiting for servers to boot and register...")

    # Start DHCP listener (background task)
    asyncio.create_task(run_dhcp_listener())

    # Keep running
    while True:
        await asyncio.sleep(60)
        logger.info(f"⏱️  Heartbeat - Provisioned: {len(provisioned_hosts)}, Pending: {len(pending_macs)}, DiaperNodes: {len(diaper_nodes)}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
