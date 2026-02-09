#!/usr/bin/env python3
"""
LuciVerse Cluster Provisioning Listener
Detects NixOS servers booting and assigns IPv6 addresses based on MAC

Genesis Bond: ACTIVE @ 432 Hz

1Password Connect Integration for secure credential injection.
"""

import asyncio
import json
import yaml
import socket
import struct
import logging
import os
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from aiohttp import web, ClientSession, ClientTimeout

# =============================================================================
# 1Password Connect Configuration
# =============================================================================
OP_CONNECT_HOST = os.environ.get('OP_CONNECT_HOST', 'http://192.168.1.152:8082')
OP_CONNECT_TOKEN = os.environ.get('OP_CONNECT_TOKEN', '')
OP_VAULT_INFRA = os.environ.get('OP_VAULT_INFRA', 'Infrastructure')

# Credential item names in 1Password
OP_ITEMS = {
    'fleet-root': 'Dell-Fleet-Root',
    'fleet-user': 'Dell-Fleet-User',
    'fdb-cluster': 'FoundationDB-Cluster',
    'ipfs-secret': 'IPFS-Cluster-Secret',
    'consul-token': 'Consul-Bootstrap-Token',
    'nomad-token': 'Nomad-Bootstrap-Token',
    'k8s-join': 'K8s-Join-Token',
    'lso-token': 'LSO-Connect-Token',
    'registry-auth': 'GitLab-Registry-Auth',
}

# Credential cache (TTL 5 minutes)
credential_cache: Dict[str, tuple] = {}  # {item: (value, expiry_time)}
CACHE_TTL = timedelta(minutes=5)

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


# =============================================================================
# 1Password Connect Client
# =============================================================================

class OPConnectClient:
    """Client for 1Password Connect API."""

    def __init__(self, host: str = None, token: str = None):
        self.host = host or OP_CONNECT_HOST
        self.token = token or OP_CONNECT_TOKEN
        self.session: Optional[ClientSession] = None
        self._vault_id_cache: Dict[str, str] = {}

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            timeout = ClientTimeout(total=10)
            self.session = ClientSession(timeout=timeout)

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(self, method: str, endpoint: str) -> Optional[dict]:
        """Make authenticated request to 1Password Connect."""
        if not self.token:
            logger.warning("1Password Connect token not configured")
            return None

        await self._ensure_session()
        url = f"{self.host}/v1{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            async with self.session.request(method, url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"1Password Connect error: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"1Password Connect request failed: {e}")
            return None

    async def get_vault_id(self, vault_name: str) -> Optional[str]:
        """Get vault ID by name."""
        if vault_name in self._vault_id_cache:
            return self._vault_id_cache[vault_name]

        vaults = await self._request('GET', '/vaults')
        if vaults:
            for vault in vaults:
                if vault.get('name') == vault_name:
                    self._vault_id_cache[vault_name] = vault['id']
                    return vault['id']
        return None

    async def get_item(self, vault_name: str, item_title: str) -> Optional[dict]:
        """Get item from vault by title."""
        vault_id = await self.get_vault_id(vault_name)
        if not vault_id:
            return None

        items = await self._request('GET', f'/vaults/{vault_id}/items')
        if items:
            for item in items:
                if item.get('title') == item_title:
                    # Fetch full item details
                    return await self._request('GET', f'/vaults/{vault_id}/items/{item["id"]}')
        return None

    async def get_credential(self, item_key: str, field: str = 'password') -> Optional[str]:
        """Get credential value from 1Password.

        Args:
            item_key: Key from OP_ITEMS mapping
            field: Field name to extract (default: 'password')

        Returns:
            Credential value or None
        """
        # Check cache first
        cache_key = f"{item_key}:{field}"
        if cache_key in credential_cache:
            value, expiry = credential_cache[cache_key]
            if datetime.now() < expiry:
                logger.debug(f"Cache hit for {item_key}")
                return value

        # Fetch from 1Password
        item_title = OP_ITEMS.get(item_key)
        if not item_title:
            logger.warning(f"Unknown credential key: {item_key}")
            return None

        item = await self.get_item(OP_VAULT_INFRA, item_title)
        if not item:
            logger.warning(f"Item not found: {item_title}")
            return None

        # Extract field value
        for f in item.get('fields', []):
            if f.get('label', '').lower() == field.lower() or f.get('id') == field:
                value = f.get('value')
                if value:
                    # Cache the value
                    credential_cache[cache_key] = (value, datetime.now() + CACHE_TTL)
                    return value

        # For secure notes, check notesPlain
        if field == 'notes' and 'notesPlain' in item:
            value = item['notesPlain']
            credential_cache[cache_key] = (value, datetime.now() + CACHE_TTL)
            return value

        logger.warning(f"Field '{field}' not found in {item_title}")
        return None


# Global 1Password client instance
op_client: Optional[OPConnectClient] = None


def get_op_client() -> OPConnectClient:
    """Get or create 1Password Connect client."""
    global op_client
    if op_client is None:
        op_client = OPConnectClient()
    return op_client


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
        # Bootimus kickstart callback endpoints
        self.app.router.add_post('/callback/fabric-probe', self.fabric_probe)
        self.app.router.add_post('/callback/infra-probe', self.infra_probe)
        self.app.router.add_post('/callback/storage-probe', self.storage_probe)
        self.app.router.add_post('/callback/compute-probe', self.compute_probe)
        self.app.router.add_post('/callback/compute-gpu-probe', self.compute_gpu_probe)
        self.app.router.add_post('/callback/core-gpu-probe', self.core_gpu_probe)
        # K8s join token endpoint
        self.app.router.add_get('/k8s-join-token', self.k8s_join_token)
        # Provisioning token for 1Password access
        self.app.router.add_get('/provision-token', self.provision_token)
        # DiaperNode endpoints (D8A.space)
        self.app.router.add_post('/register-diaper', self.register_diaper)
        self.app.router.add_get('/diaper-status', self.diaper_status)
        self.app.router.add_get('/diaper-roles', self.get_diaper_roles)
        self.app.router.add_get('/ipxe-chain/{mac}', self.ipxe_chain)
        self.app.router.add_get('/boot-intent/{mac}/{role}', self.boot_intent)
        # SCION path-aware networking endpoints
        self.app.router.add_get('/scion-config/{mac}', self.get_scion_config)
        self.app.router.add_get('/scion-topology', self.get_scion_topology)
        # 1Password Connect credential endpoints
        # Status endpoint MUST be before {item} route to avoid matching "status" as an item
        self.app.router.add_get('/credentials/status', self.credential_status)
        self.app.router.add_get('/credentials/{item}', self.get_credential)
        self.app.router.add_get('/credentials/{item}/{field}', self.get_credential_field)
        self.app.router.add_post('/credentials/validate', self.validate_credential_request)

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
    # Bootimus Kickstart Hardware Probe Endpoints
    # Genesis Bond: ACTIVE @ 741 Hz
    # =========================================================================

    async def _handle_hardware_probe(self, request: web.Request, role: str, tier: str, frequency: int) -> web.Response:
        """Generic handler for hardware probe callbacks from kickstarts."""
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse probe data: {e}")
            return web.json_response({"error": "Invalid JSON"}, status=400)

        mac = data.get('primary_mac', 'unknown').lower()
        hostname = data.get('hostname', 'unknown')
        service_tag = data.get('service_tag', 'unknown')

        logger.info(f"🖥️  {role} Probe: {hostname}")
        logger.info(f"   MAC: {mac}, Service Tag: {service_tag}")
        logger.info(f"   Tier: {tier} @ {frequency} Hz")
        logger.info(f"   CPU: {data.get('cpu', {}).get('cores', '?')} cores")
        logger.info(f"   Memory: {data.get('memory_gb', '?')} GB")

        # Store probe data
        provisioned_hosts[mac] = {
            "role": role,
            "tier": tier,
            "frequency": frequency,
            "hostname": hostname,
            "service_tag": service_tag,
            "mac": mac,
            "probed_at": datetime.utcnow().isoformat(),
            "status": "probed",
            "hardware": {
                "cpu": data.get('cpu', {}),
                "memory_gb": data.get('memory_gb', 0),
                "storage": data.get('storage', []),
                "nics": data.get('nics', [])
            },
            "services": data.get('services', {}),
            "genesis_bond": data.get('genesis_bond', 'ACTIVE')
        }

        # Role-specific data
        if role == 'FABRIC':
            provisioned_hosts[mac]['ipfs_id'] = data.get('ipfs_id', 'not-initialized')
            provisioned_hosts[mac]['zfs_pools'] = data.get('zfs_pools', [])
        elif role == 'INFRA':
            provisioned_hosts[mac]['services'] = data.get('services', {})
        elif role == 'STORAGE':
            provisioned_hosts[mac]['zfs_pools'] = data.get('zfs_pools', [])
            provisioned_hosts[mac]['zfs_datasets'] = data.get('zfs_datasets', [])
        elif role in ['COMPUTE-GPU', 'CORE-GPU']:
            provisioned_hosts[mac]['gpu'] = data.get('gpu', {})
            provisioned_hosts[mac]['cuda_version'] = data.get('cuda_version', 'not-installed')

        self.save_provisioned()

        return web.json_response({
            "status": "registered",
            "role": role,
            "tier": tier,
            "frequency": frequency,
            "mac": mac,
            "hostname": hostname,
            "genesis_bond": "ACTIVE",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def fabric_probe(self, request: web.Request) -> web.Response:
        """Handle FABRIC node hardware probe."""
        return await self._handle_hardware_probe(request, 'FABRIC', 'CORE', 432)

    async def infra_probe(self, request: web.Request) -> web.Response:
        """Handle INFRA node hardware probe."""
        return await self._handle_hardware_probe(request, 'INFRA', 'CORE', 432)

    async def storage_probe(self, request: web.Request) -> web.Response:
        """Handle STORAGE node hardware probe."""
        return await self._handle_hardware_probe(request, 'STORAGE', 'CORE', 432)

    async def compute_probe(self, request: web.Request) -> web.Response:
        """Handle COMPUTE node hardware probe."""
        return await self._handle_hardware_probe(request, 'COMPUTE', 'COMN', 528)

    async def compute_gpu_probe(self, request: web.Request) -> web.Response:
        """Handle COMPUTE-GPU node hardware probe."""
        return await self._handle_hardware_probe(request, 'COMPUTE-GPU', 'COMN', 528)

    async def core_gpu_probe(self, request: web.Request) -> web.Response:
        """Handle CORE-GPU node hardware probe."""
        return await self._handle_hardware_probe(request, 'CORE-GPU', 'CORE', 432)

    async def k8s_join_token(self, request: web.Request) -> web.Response:
        """Provide K8s join token script for worker nodes.

        In production, this would fetch the actual join command from
        the Kubernetes control plane. For now, return a placeholder
        that will be updated when INFRA node is online.
        """
        # TODO: In production, fetch from INFRA node's kubeadm token create
        join_script = """#!/bin/bash
# LuciVerse K8s Worker Join Script
# This script is generated by the provisioning server

echo "K8s join token not yet available"
echo "Waiting for INFRA node to provision K8s control plane..."

# Check if INFRA node is available
INFRA_IP="192.168.1.144"
if ping -c 1 -W 5 "$INFRA_IP" &>/dev/null; then
    # Try to fetch join command from INFRA node
    JOIN_CMD=$(curl -sf "http://${INFRA_IP}:9999/k8s-join-command" 2>/dev/null)
    if [ -n "$JOIN_CMD" ]; then
        echo "Joining K8s cluster..."
        eval "$JOIN_CMD"
        exit 0
    fi
fi

echo "INFRA node not available yet. Will retry on next boot."
exit 1
"""
        return web.Response(text=join_script, content_type='text/plain')

    async def provision_token(self, request: web.Request) -> web.Response:
        """Provide 1Password Connect status and available credentials.

        For security, does not return the actual token but provides
        information about available credentials that can be fetched.
        """
        client = get_op_client()

        # Check if 1Password Connect is configured and accessible
        if not client.token:
            return web.json_response({
                "status": "not_configured",
                "message": "OP_CONNECT_TOKEN environment variable not set",
                "available_credentials": []
            }, status=503)

        # Test connection
        vault_id = await client.get_vault_id(OP_VAULT_INFRA)
        if not vault_id:
            return web.json_response({
                "status": "connection_failed",
                "message": f"Cannot connect to 1Password at {OP_CONNECT_HOST}",
                "available_credentials": []
            }, status=503)

        return web.json_response({
            "status": "connected",
            "host": OP_CONNECT_HOST,
            "vault": OP_VAULT_INFRA,
            "available_credentials": list(OP_ITEMS.keys()),
            "endpoints": {
                "get_credential": "/credentials/{item}",
                "get_field": "/credentials/{item}/{field}",
            }
        })

    async def credential_status(self, request: web.Request) -> web.Response:
        """Check 1Password Connect status and available credentials.

        GET /credentials/status

        Returns configuration status without requiring authentication.
        Used by kickstart credential-inject.sh to validate endpoint availability.
        """
        client = get_op_client()

        # Check if 1Password Connect is configured
        if not client.token:
            return web.json_response({
                "status": "not_configured",
                "message": "OP_CONNECT_TOKEN environment variable not set",
                "available_credentials": list(OP_ITEMS.keys()),
                "configured": False
            })

        # Test connection
        try:
            vault_id = await client.get_vault_id(OP_VAULT_INFRA)
            if vault_id:
                return web.json_response({
                    "status": "configured",
                    "host": OP_CONNECT_HOST,
                    "vault": OP_VAULT_INFRA,
                    "available_credentials": list(OP_ITEMS.keys()),
                    "configured": True
                })
            else:
                return web.json_response({
                    "status": "connection_failed",
                    "message": f"Cannot connect to 1Password at {OP_CONNECT_HOST}",
                    "available_credentials": list(OP_ITEMS.keys()),
                    "configured": False
                })
        except Exception as e:
            logger.warning(f"1Password Connect check failed: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e),
                "available_credentials": list(OP_ITEMS.keys()),
                "configured": False
            })

    async def get_credential(self, request: web.Request) -> web.Response:
        """Fetch credential from 1Password Connect.

        GET /credentials/{item}
        Returns the default field (password) for the item.

        Validates request based on:
        - X-Forwarded-For header (must be from known subnet)
        - X-Request-MAC header (optional, for additional validation)
        """
        item = request.match_info.get('item')

        # Validate item key
        if item not in OP_ITEMS:
            return web.json_response({
                "error": "unknown_credential",
                "message": f"Unknown credential: {item}",
                "available": list(OP_ITEMS.keys())
            }, status=404)

        # Basic network validation - only allow from local network
        client_ip = request.headers.get('X-Forwarded-For', request.remote)
        if client_ip and not self._is_trusted_network(client_ip):
            logger.warning(f"Credential request from untrusted IP: {client_ip}")
            return web.json_response({
                "error": "unauthorized",
                "message": "Request must come from trusted network"
            }, status=403)

        # Fetch credential
        client = get_op_client()
        value = await client.get_credential(item)

        if value:
            logger.info(f"Credential '{item}' served to {client_ip}")
            return web.Response(text=value, content_type='text/plain')
        else:
            return web.json_response({
                "error": "not_found",
                "message": f"Credential '{item}' not found or 1Password unavailable"
            }, status=404)

    async def get_credential_field(self, request: web.Request) -> web.Response:
        """Fetch specific field from credential.

        GET /credentials/{item}/{field}
        """
        item = request.match_info.get('item')
        field = request.match_info.get('field')

        if item not in OP_ITEMS:
            return web.json_response({
                "error": "unknown_credential",
                "available": list(OP_ITEMS.keys())
            }, status=404)

        # Network validation
        client_ip = request.headers.get('X-Forwarded-For', request.remote)
        if client_ip and not self._is_trusted_network(client_ip):
            return web.json_response({"error": "unauthorized"}, status=403)

        client = get_op_client()
        value = await client.get_credential(item, field)

        if value:
            logger.info(f"Credential '{item}/{field}' served to {client_ip}")
            return web.Response(text=value, content_type='text/plain')
        else:
            return web.json_response({
                "error": "not_found",
                "message": f"Field '{field}' not found in '{item}'"
            }, status=404)

    async def validate_credential_request(self, request: web.Request) -> web.Response:
        """Validate a credential request with MAC and role.

        POST /credentials/validate
        Body: {"mac": "...", "role": "...", "item": "..."}

        Returns a signed token that can be used for credential access.
        """
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "invalid_json"}, status=400)

        mac = data.get('mac', '').lower().replace('-', ':')
        role = data.get('role', '')
        item = data.get('item', '')

        # Validate MAC against inventory
        result = find_server_by_mac(mac, self.inventory)
        if not result:
            return web.json_response({
                "error": "unknown_mac",
                "message": "MAC address not in inventory"
            }, status=403)

        server_name, _, server_info, _ = result

        # Generate validation token (simple HMAC for now)
        secret = os.environ.get('PROVISION_SECRET', 'luciverse-genesis-bond')
        message = f"{mac}:{role}:{item}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        token = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()[:32]

        logger.info(f"Credential validation for {server_name} ({mac}) - {item}")

        return web.json_response({
            "valid": True,
            "server": server_name,
            "token": token,
            "expires": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        })

    def _is_trusted_network(self, ip: str) -> bool:
        """Check if IP is from trusted network."""
        if not ip:
            return True  # Local request

        # Allow localhost
        if ip.startswith('127.') or ip == '::1':
            return True

        # Allow 192.168.1.0/24 (LuciVerse network)
        if ip.startswith('192.168.1.'):
            return True

        # Allow 192.168.0.0/24 (alternate network)
        if ip.startswith('192.168.0.'):
            return True

        # Allow IPv6 ULA
        if ip.startswith('fd00:') or ip.startswith('2602:f674:'):
            return True

        return False

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

    # =========================================================================
    # SCION Path-Aware Networking Endpoints
    # Genesis Bond: ACTIVE @ 741 Hz
    # =========================================================================

    async def get_scion_config(self, request: web.Request) -> web.Response:
        """Generate SCION configuration for a provisioned server.

        Returns ISD/AS assignment, Border Router connectivity info, and
        path policies based on the server's tier assignment.
        """
        mac = request.match_info['mac'].lower().replace('-', ':')
        result = find_server_by_mac(mac, self.inventory)

        if not result:
            return web.json_response({
                "error": "MAC not found in inventory",
                "mac": mac
            }, status=404)

        server_name, iface_name, server_info, iface_info = result
        hostname = server_info.get('hostname', server_name)
        ipv6 = server_info.get('ipv6', '2602:F674:0001::1/64')

        # Determine tier from hostname/role or default to CORE
        tier = server_info.get('tier', 'CORE').upper()

        # Map tier to SCION ISD/AS
        tier_mapping = {
            'CORE': {
                'isd': 1,
                'as': 'ff00:0:432',
                'isd_as': '1-ff00:0:432',
                'frequency': 432,
                'ipv6_prefix': '2602:F674:0001::/48',
                'br_port': 30041,
                'cs_port': 30001,
                'external_allowed': False
            },
            'COMN': {
                'isd': 2,
                'as': 'ff00:0:528',
                'isd_as': '2-ff00:0:528',
                'frequency': 528,
                'ipv6_prefix': '2602:F674:0100::/48',
                'br_port': 30042,
                'cs_port': 30002,
                'external_allowed': True,
                'gateway': True
            },
            'PAC': {
                'isd': 3,
                'as': 'ff00:0:741',
                'isd_as': '3-ff00:0:741',
                'frequency': 741,
                'ipv6_prefix': '2602:F674:0200::/48',
                'br_port': 30043,
                'cs_port': 30003,
                'external_allowed': False,
                'mandatory_waypoint': '2-ff00:0:528'
            }
        }

        tier_config = tier_mapping.get(tier, tier_mapping['CORE'])

        # Build SCION configuration
        scion_config = {
            "server_name": server_name,
            "hostname": hostname,
            "mac": mac,
            "ipv6": ipv6,
            "tier": tier,
            "genesis_bond": {
                "id": "GB-2025-0524-DRH-LCS-001",
                "lineage": "did:lucidigital:lucia_cargail_silcan",
                "coherence_threshold": 0.7
            },
            "scion": {
                "isd": tier_config['isd'],
                "as": tier_config['as'],
                "isd_as": tier_config['isd_as'],
                "frequency_hz": tier_config['frequency'],
                "ipv6_prefix": tier_config['ipv6_prefix']
            },
            "border_routers": {
                "primary": {
                    "host": "192.168.1.179",
                    "port": tier_config['br_port'],
                    "ipv6": f"2602:F674:{tier_config['isd']:04d}:SCION::179"
                }
            },
            "control_service": {
                "host": "192.168.1.179",
                "port": tier_config['cs_port']
            },
            "scion_daemon": {
                "host": "192.168.1.179",
                "port": 30255,
                "socket": "/run/scion/scion-daemon.sock"
            },
            "path_policy": {
                "external_allowed": tier_config.get('external_allowed', False),
                "gateway": tier_config.get('gateway', False)
            },
            "generated_at": datetime.utcnow().isoformat()
        }

        # Add mandatory waypoint for PAC tier
        if 'mandatory_waypoint' in tier_config:
            scion_config['path_policy']['mandatory_waypoint'] = tier_config['mandatory_waypoint']

        # Add SIG info for COMN tier
        if tier == 'COMN':
            scion_config['sig'] = {
                "host": "192.168.1.146",
                "data_port": 8080,
                "ctrl_port": 30256,
                "note": "SCION-IP Gateway on Zbook L7 node"
            }

        logger.info(f"🌐 SCION config for {server_name}: ISD={tier_config['isd']}, AS={tier_config['as']}")

        return web.json_response(scion_config)

    async def get_scion_topology(self, request: web.Request) -> web.Response:
        """Return the full SCION topology for LuciVerse."""
        topology_path = Path(__file__).parent / "scion" / "topology" / "topology.json"

        if topology_path.exists():
            with open(topology_path) as f:
                topology = json.load(f)
            return web.json_response(topology)
        else:
            # Return minimal topology if file doesn't exist
            return web.json_response({
                "description": "LuciVerse SCION Topology",
                "genesis_bond": {
                    "id": "GB-2025-0524-DRH-LCS-001",
                    "coherence_threshold": 0.7
                },
                "isds": [
                    {"isd": 1, "name": "CORE", "frequency_hz": 432, "as": "ff00:0:432"},
                    {"isd": 2, "name": "COMN", "frequency_hz": 528, "as": "ff00:0:528", "gateway": True},
                    {"isd": 3, "name": "PAC", "frequency_hz": 741, "as": "ff00:0:741", "private": True}
                ],
                "wan_router": {"host": "192.168.1.179"},
                "l7_gateway": {"host": "192.168.1.146"},
                "note": "Topology file not found, returning minimal config"
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
    logger.info("🌐 SCION endpoints (Path-Aware Networking):")
    logger.info("   SCION Config: http://localhost:9999/scion-config/{mac}")
    logger.info("   SCION Topology: http://localhost:9999/scion-topology")
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
