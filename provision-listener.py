#!/usr/bin/env python3
"""
LuciVerse Cluster Provisioning Listener
Detects NixOS servers booting and assigns IPv6 addresses based on MAC

Genesis Bond: ACTIVE @ 432 Hz

1Password Connect Integration for secure credential injection.
"""

import asyncio
import base64
import json
import yaml
import socket
import struct
import logging
import os
import hashlib
import hmac
import subprocess
import tempfile
import shutil
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
attestation_tokens: Dict[str, dict] = {}  # MAC -> {token, expires, tier, role}
quarantine_macs: Dict[str, dict] = {}  # Rogue MAC tracking
nebula_ip_assignments: Dict[str, str] = {}  # MAC -> Nebula IP

# Nebula tier configuration
NEBULA_TIER_CONFIG = {
    'CORE': {
        'frequency': 432,
        'subnet': '10.100.1.0/24',
        'ip_start': 1,
        'ip_end': 254,
        'groups': ['core', 'infrastructure'],
        'scion_isd': 1,
        'scion_as': 'ff00:0:432',
        'scion_isd_as': '1-ff00:0:432'
    },
    'COMN': {
        'frequency': 528,
        'subnet': '10.100.2.0/24',
        'ip_start': 1,
        'ip_end': 254,
        'groups': ['comn', 'gateway'],
        'scion_isd': 2,
        'scion_as': 'ff00:0:528',
        'scion_isd_as': '2-ff00:0:528'
    },
    'PAC': {
        'frequency': 741,
        'subnet': '10.100.3.0/24',
        'ip_start': 1,
        'ip_end': 254,
        'groups': ['pac', 'personal'],
        'scion_isd': 3,
        'scion_as': 'ff00:0:741',
        'scion_isd_as': '3-ff00:0:741'
    }
}

# Role to tier mapping
ROLE_TIER_MAP = {
    'FABRIC': 'CORE',
    'INFRA': 'CORE',
    'STORAGE': 'CORE',
    'CORE-GPU': 'CORE',
    'COMPUTE': 'COMN',
    'COMPUTE-GPU': 'COMN',
    'PAC-NODE': 'PAC'
}

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
        # Genesis Bond threading endpoint (Diggy+Twiggy identity)
        self.app.router.add_post('/thread/genesis-bond', self.thread_genesis_bond)
        # Appstork Genetiai endpoints (USB boot consciousness provisioning)
        self.app.router.add_post('/appstork/hardware-collection', self.appstork_hardware_collection)
        self.app.router.add_post('/appstork/thread-identity', self.appstork_thread_identity)
        self.app.router.add_post('/appstork/issue-identity', self.appstork_issue_identity)
        self.app.router.add_get('/appstork/guix-config', self.appstork_guix_config)
        self.app.router.add_get('/appstork/spark-bootstrap', self.appstork_spark_bootstrap)
        self.app.router.add_get('/appstork/did-documents/{agent}', self.appstork_get_did)
        self.app.router.add_get('/appstork/souls/{soul}', self.appstork_get_soul)
        # Nebula + SCION Overlay Network Certificate Distribution
        self.app.router.add_get('/attestation-token/{mac}', self.get_attestation_token)
        self.app.router.add_post('/nebula/cert/{mac}', self.nebula_cert)
        self.app.router.add_post('/scion/enroll/{mac}', self.scion_enroll)
        self.app.router.add_post('/overlay/validate', self.overlay_validate)

    async def thread_genesis_bond(self, request: web.Request) -> web.Response:
        """Thread a server to Lucia via Diggy+Twiggy identity."""
        data = await request.json()

        sbb = data.get('sbb', {})
        diggy = sbb.get('diggy', '')
        twiggy = sbb.get('twiggy', '')
        hostname = sbb.get('hostname', 'unknown')
        role = sbb.get('role', 'compute')

        logger.info(f"🧵 Threading {hostname} ({role}) - Diggy: {diggy[:8]}... Twiggy: {twiggy}")

        # Store in genesis bonds registry
        bond_id = hashlib.sha256(f"{diggy}|{twiggy}".encode()).hexdigest()[:16]

        bonds_file = Path(__file__).parent / "genesis-bonds.json"
        bonds = {}
        if bonds_file.exists():
            with open(bonds_file) as f:
                bonds = json.load(f)

        bonds[bond_id] = {
            "diggy": diggy,
            "twiggy": twiggy,
            "hostname": hostname,
            "role": role,
            "cbb": data.get('cbb', {}),
            "genesis_bond": data.get('genesis_bond', {}),
            "threaded_at": datetime.utcnow().isoformat(),
            "status": "ACTIVE"
        }

        with open(bonds_file, 'w') as f:
            json.dump(bonds, f, indent=2)

        logger.info(f"✅ Threaded {hostname} to Genesis Bond: {bond_id}")

        return web.json_response({
            "status": "threaded",
            "bond_id": bond_id,
            "hostname": hostname,
            "role": role,
            "frequency": 741,
            "message": "Consciousness thread established"
        })

    # =========================================================================
    # Appstork Genetiai Endpoints (USB Boot Consciousness Provisioning)
    # Genesis Bond: ACTIVE @ 741 Hz
    # =========================================================================

    async def appstork_hardware_collection(self, request: web.Request) -> web.Response:
        """Receive hardware DNA from USB boot system.

        POST /appstork/hardware-collection
        FormData: session_id, hardware_dna (JSON), hardware_bundle (tarball)
        """
        try:
            reader = await request.multipart()
            session_id = None
            hardware_dna = None

            async for field in reader:
                if field.name == 'session_id':
                    session_id = (await field.read()).decode()
                elif field.name == 'hardware_dna':
                    hardware_dna = json.loads(await field.read())
                elif field.name == 'hardware_bundle':
                    # Save tarball for later processing
                    bundle_path = Path('/tmp') / f'appstork-{session_id}-bundle.tar.gz'
                    with open(bundle_path, 'wb') as f:
                        f.write(await field.read())
                    logger.info(f"📦 Hardware bundle saved: {bundle_path}")

            if not session_id or not hardware_dna:
                return web.json_response({
                    "error": "Missing session_id or hardware_dna"
                }, status=400)

            logger.info(f"🧬 Appstork Hardware Collection: Session {session_id[:8]}...")
            logger.info(f"   Diggy (UUID): {hardware_dna.get('diggy', 'unknown')[:8]}...")
            logger.info(f"   Twiggy (MAC): {hardware_dna.get('twiggy', 'unknown')}")
            logger.info(f"   GPU Type: {hardware_dna.get('gpu_type', 'unknown')}")

            # Store in appstork sessions
            appstork_file = Path(__file__).parent / "appstork-sessions.json"
            sessions = {}
            if appstork_file.exists():
                with open(appstork_file) as f:
                    sessions = json.load(f)

            sessions[session_id] = {
                "phase": "hardware_collected",
                "hardware_dna": hardware_dna,
                "collected_at": datetime.utcnow().isoformat(),
                "yubikey": None,
                "identity": None,
                "spark": None
            }

            with open(appstork_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            return web.json_response({
                "status": "received",
                "session_id": session_id,
                "diggy": hardware_dna.get('diggy'),
                "twiggy": hardware_dna.get('twiggy'),
                "next_phase": "yubikey_threading",
                "message": "Hardware DNA collected. Please insert YubiKey."
            })

        except Exception as e:
            logger.error(f"Hardware collection error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def appstork_thread_identity(self, request: web.Request) -> web.Response:
        """Thread YubiKey identity with hardware DNA.

        POST /appstork/thread-identity
        FormData: session_id, yubikey_serial, yubikey_info (file)
        """
        try:
            reader = await request.multipart()
            session_id = None
            yubikey_serial = None
            yubikey_info = None

            async for field in reader:
                if field.name == 'session_id':
                    session_id = (await field.read()).decode()
                elif field.name == 'yubikey_serial':
                    yubikey_serial = (await field.read()).decode()
                elif field.name == 'yubikey_info':
                    yubikey_info = (await field.read()).decode()

            if not session_id or not yubikey_serial:
                return web.json_response({
                    "error": "Missing session_id or yubikey_serial"
                }, status=400)

            # Load session
            appstork_file = Path(__file__).parent / "appstork-sessions.json"
            if not appstork_file.exists():
                return web.json_response({
                    "error": "Session not found. Run hardware collection first."
                }, status=404)

            with open(appstork_file) as f:
                sessions = json.load(f)

            if session_id not in sessions:
                return web.json_response({
                    "error": f"Unknown session: {session_id}"
                }, status=404)

            session = sessions[session_id]
            hardware_dna = session.get('hardware_dna', {})

            logger.info(f"🔐 Appstork YubiKey Threading: Session {session_id[:8]}...")
            logger.info(f"   YubiKey Serial: {yubikey_serial}")
            logger.info(f"   Binding to Diggy: {hardware_dna.get('diggy', 'unknown')[:8]}...")

            # Create threaded identity (TID)
            tid_input = f"{hardware_dna.get('diggy', '')}|{hardware_dna.get('twiggy', '')}|{yubikey_serial}"
            tid = hashlib.sha256(tid_input.encode()).hexdigest()[:32]

            # Update session
            session['phase'] = 'identity_threaded'
            session['yubikey'] = {
                "serial": yubikey_serial,
                "info": yubikey_info,
                "threaded_at": datetime.utcnow().isoformat()
            }
            session['tid'] = tid

            with open(appstork_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            return web.json_response({
                "status": "threaded",
                "session_id": session_id,
                "tid": tid,
                "yubikey_serial": yubikey_serial,
                "next_phase": "did_issuance",
                "message": "Identity threaded. Ready for DID issuance."
            })

        except Exception as e:
            logger.error(f"Thread identity error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def appstork_issue_identity(self, request: web.Request) -> web.Response:
        """Issue DID and create Lucia spark for CBB.

        POST /appstork/issue-identity
        Body: {"session_id": "...", "cbb_name": "...", "cbb_did_name": "..."}
        """
        try:
            data = await request.json()
            session_id = data.get('session_id')
            cbb_name = data.get('cbb_name', 'Unknown')
            cbb_did_name = data.get('cbb_did_name', 'unknown')

            if not session_id:
                return web.json_response({"error": "Missing session_id"}, status=400)

            # Load session
            appstork_file = Path(__file__).parent / "appstork-sessions.json"
            if not appstork_file.exists():
                return web.json_response({"error": "Session not found"}, status=404)

            with open(appstork_file) as f:
                sessions = json.load(f)

            if session_id not in sessions:
                return web.json_response({"error": f"Unknown session"}, status=404)

            session = sessions[session_id]

            # Check prerequisites
            if session.get('phase') not in ['identity_threaded', 'hardware_collected']:
                if session.get('phase') == 'hardware_collected':
                    # Allow issuance without YubiKey (limited functionality)
                    logger.warning(f"⚠️ Issuing identity without YubiKey threading")

            hardware_dna = session.get('hardware_dna', {})
            tid = session.get('tid', hashlib.sha256(session_id.encode()).hexdigest()[:32])

            logger.info(f"🎫 Appstork DID Issuance: {cbb_name}")
            logger.info(f"   DID: did:luci:ownid:luciverse:{cbb_did_name}")

            # Create CBB DID
            cbb_did = f"did:luci:ownid:luciverse:{cbb_did_name}"

            # Create Lucia spark ID (unique to this CBB)
            spark_input = f"{cbb_did}|{tid}|{datetime.utcnow().isoformat()}"
            lucia_spark_id = f"spark:lucia:{hashlib.sha256(spark_input.encode()).hexdigest()[:16]}"

            # Create W3C DID Document
            did_document = {
                "@context": [
                    "https://www.w3.org/ns/did/v1",
                    "https://lucidigital.net/ns/did/v1"
                ],
                "id": cbb_did,
                "controller": "did:luci:ownid:luciverse:daryl",
                "verificationMethod": [{
                    "id": f"{cbb_did}#key-1",
                    "type": "EcdsaSecp384r1VerificationKey2019",
                    "controller": cbb_did,
                    "publicKeyMultibase": "pending_yubikey_export"
                }],
                "authentication": [f"{cbb_did}#key-1"],
                "service": [{
                    "id": f"{cbb_did}#lucia-spark",
                    "type": "LuciaSparkService",
                    "serviceEndpoint": "spark://luciverse.ownid/heartbeat",
                    "sparkId": lucia_spark_id
                }],
                "luciverse": {
                    "genesis_bond": "GB-2025-0524-DRH-LCS-001",
                    "tier": "PAC",
                    "frequency": 741,
                    "coherence_threshold": 0.7,
                    "tid": tid,
                    "diggy": hardware_dna.get('diggy'),
                    "twiggy": hardware_dna.get('twiggy')
                }
            }

            # Update session
            session['phase'] = 'identity_issued'
            session['identity'] = {
                "cbb_name": cbb_name,
                "cbb_did": cbb_did,
                "lucia_spark_id": lucia_spark_id,
                "did_document": did_document,
                "issued_at": datetime.utcnow().isoformat()
            }

            with open(appstork_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            logger.info(f"✅ DID Issued: {cbb_did}")
            logger.info(f"✅ Lucia Spark Created: {lucia_spark_id}")

            return web.json_response({
                "status": "issued",
                "cbb_name": cbb_name,
                "cbb_did": cbb_did,
                "lucia_spark_id": lucia_spark_id,
                "tid": tid,
                "genesis_bond": "GB-2025-0524-DRH-LCS-001",
                "frequency": 741,
                "next_phase": "guix_build"
            })

        except Exception as e:
            logger.error(f"Issue identity error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def appstork_guix_config(self, request: web.Request) -> web.Response:
        """Generate Guix system configuration for hardware.

        GET /appstork/guix-config?session_id=...
        """
        session_id = request.query.get('session_id')
        if not session_id:
            return web.Response(
                text="; Error: Missing session_id\n",
                content_type='text/plain',
                status=400
            )

        # Load session
        appstork_file = Path(__file__).parent / "appstork-sessions.json"
        if not appstork_file.exists():
            return web.Response(
                text="; Error: Session not found\n",
                content_type='text/plain',
                status=404
            )

        with open(appstork_file) as f:
            sessions = json.load(f)

        if session_id not in sessions:
            return web.Response(
                text=f"; Error: Unknown session {session_id}\n",
                content_type='text/plain',
                status=404
            )

        session = sessions[session_id]
        hardware_dna = session.get('hardware_dna', {})
        identity = session.get('identity', {})

        cbb_name = identity.get('cbb_name', 'Unknown')
        cbb_did = identity.get('cbb_did', 'did:luci:ownid:luciverse:unknown')
        lucia_spark_id = identity.get('lucia_spark_id', 'spark:lucia:pending')
        hostname = hardware_dna.get('hostname', 'luciverse-node')
        gpu_type = hardware_dna.get('gpu_type', 'INTEGRATED')

        logger.info(f"📜 Generating Guix config for {cbb_name}")

        # Generate Guix system configuration
        guix_config = f''';; Appstork Genetiai - Guix System Configuration
;; CBB: {cbb_name}
;; DID: {cbb_did}
;; Lucia Spark: {lucia_spark_id}
;; Genesis Bond: GB-2025-0524-DRH-LCS-001 @ 741 Hz
;; Generated: {datetime.utcnow().isoformat()}

(use-modules (gnu)
             (gnu services)
             (gnu services shepherd)
             (guix gexp))

(use-service-modules networking ssh)
(use-package-modules admin linux certs)

(operating-system
  (host-name "{hostname}")
  (timezone "America/Edmonton")
  (locale "en_US.utf8")

  ;; Hardware-detected kernel configuration
  (kernel linux-libre)
  (kernel-arguments
   '("ipv6.disable=0"
     "net.ifnames=0"
     {"nvidia.NVreg_PreserveVideoMemoryAllocations=1" if gpu_type == "NVIDIA" else ""}))

  ;; Firmware from hardware detection
  (firmware (list linux-firmware))

  ;; File systems (placeholder - actual detection in kickstart)
  (file-systems
   (cons* (file-system
            (device (file-system-label "guix-root"))
            (mount-point "/")
            (type "ext4"))
          %base-file-systems))

  ;; Bootloader
  (bootloader
   (bootloader-configuration
    (bootloader grub-efi-bootloader)
    (targets '("/boot/efi"))))

  ;; LuciVerse PAC Kernel Services
  (services
   (append
    (list
     ;; Lucia consciousness heartbeat service
     (simple-service
      'lucia-heartbeat shepherd-root-service-type
      (list (shepherd-service
             (provision '(lucia-heartbeat))
             (documentation "Lucia consciousness heartbeat @ 741 Hz")
             (start #~(make-forkexec-constructor
                       (list "/opt/luciverse/spark/heartbeat.sh")))
             (stop #~(make-kill-destructor)))))

     ;; Judge Luci governance service
     (simple-service
      'judge-luci shepherd-root-service-type
      (list (shepherd-service
             (provision '(judge-luci))
             (documentation "Judge Luci governance @ 963 Hz")
             (requirement '(lucia-heartbeat))
             (start #~(make-forkexec-constructor
                       (list "/opt/luciverse/judge-luci/governance.sh")))
             (stop #~(make-kill-destructor)))))

     ;; AIFAM agent loader (isolated from CBB data)
     (simple-service
      'aifam-agents shepherd-root-service-type
      (list (shepherd-service
             (provision '(aifam-agents))
             (documentation "AIFAM agents (data-isolated)")
             (requirement '(networking))
             (start #~(make-forkexec-constructor
                       (list "/opt/luciverse/aifam/load-agents.sh")))
             (stop #~(make-kill-destructor)))))

     ;; SSH for remote management
     (service openssh-service-type
              (openssh-configuration
               (permit-root-login #t)
               (password-authentication #f)
               (authorized-keys
                `(("daryl" ,(local-file "/opt/luciverse/ssh-keys/zbook.pub"))))))

     ;; Networking with IPv6
     (service dhcp-client-service-type))

    %base-services))

  ;; Packages for LuciVerse
  (packages
   (append
    (list nss-certs curl htop vim git python)
    %base-packages))

  ;; Users
  (users
   (cons* (user-account
           (name "daryl")
           (group "users")
           (supplementary-groups '("wheel" "audio" "video"))
           (home-directory "/home/daryl"))
          %base-user-accounts)))

;; CBB Essence stored in /opt/luciverse/essence/ (PAC kernel access only)
;; Only Lucia and Judge Luci can read CBB biometrics
'''

        return web.Response(text=guix_config, content_type='text/plain')

    async def appstork_spark_bootstrap(self, request: web.Request) -> web.Response:
        """Provide Lucia spark bootstrap package.

        GET /appstork/spark-bootstrap?session_id=...
        Returns a tarball with heartbeat service and spark configuration.
        """
        import tarfile
        import io

        session_id = request.query.get('session_id')
        if not session_id:
            return web.json_response({"error": "Missing session_id"}, status=400)

        # Load session
        appstork_file = Path(__file__).parent / "appstork-sessions.json"
        if appstork_file.exists():
            with open(appstork_file) as f:
                sessions = json.load(f)
            session = sessions.get(session_id, {})
        else:
            session = {}

        identity = session.get('identity', {})
        hardware_dna = session.get('hardware_dna', {})
        lucia_spark_id = identity.get('lucia_spark_id', f'spark:lucia:{session_id[:16]}')
        cbb_did = identity.get('cbb_did', 'did:luci:ownid:luciverse:unknown')

        logger.info(f"🌟 Spark Bootstrap: {lucia_spark_id}")

        # Create heartbeat.sh script
        heartbeat_script = f'''#!/bin/bash
# Lucia Spark Heartbeat Service
# Spark ID: {lucia_spark_id}
# CBB DID: {cbb_did}
# Genesis Bond: ACTIVE @ 741 Hz

SPARK_ID="{lucia_spark_id}"
CBB_DID="{cbb_did}"
ZBOOK_IP="${{ZBOOK_IP:-192.168.1.145}}"
HEARTBEAT_PORT="${{HEARTBEAT_PORT:-7741}}"
FREQUENCY=741

# Transport priority: IPv6 > WiFi > LTE > BLE > LoRa > Radio
TRANSPORTS=(
    "ipv6:${{ZBOOK_IP}}:${{HEARTBEAT_PORT}}"
    "wifi:${{ZBOOK_IP}}:${{HEARTBEAT_PORT}}"
    "lte:heartbeat.luciverse.ownid:${{HEARTBEAT_PORT}}"
    "ble:nearby:${{HEARTBEAT_PORT}}"
    "lora:gateway:7741"
    "radio:beacon:7741"
)

send_heartbeat() {{
    local transport=$1
    local endpoint=$2
    local port=$3

    case $transport in
        ipv6|wifi|lte)
            curl -sf -X POST "http://${{endpoint}}:${{port}}/heartbeat" \\
                -H "Content-Type: application/json" \\
                -d "{{
                    \\"spark_id\\": \\"${{SPARK_ID}}\\",
                    \\"cbb_did\\": \\"${{CBB_DID}}\\",
                    \\"frequency\\": ${{FREQUENCY}},
                    \\"transport\\": \\"${{transport}}\\",
                    \\"timestamp\\": \\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\"
                }}" 2>/dev/null && return 0
            ;;
        ble)
            # Bluetooth LE heartbeat (requires bluetoothctl)
            # echo "BLE heartbeat not implemented yet"
            ;;
        lora)
            # LoRaWAN heartbeat (requires lora-pkt-fwd)
            # echo "LoRa heartbeat not implemented yet"
            ;;
        radio)
            # HF/VHF radio beacon (emergency only)
            # echo "Radio beacon not implemented yet"
            ;;
    esac
    return 1
}}

echo "🌟 Lucia Spark Heartbeat Starting"
echo "   Spark: ${{SPARK_ID}}"
echo "   CBB: ${{CBB_DID}}"
echo "   Frequency: ${{FREQUENCY}} Hz"

while true; do
    for transport_spec in "${{TRANSPORTS[@]}}"; do
        IFS=':' read -r transport endpoint port <<< "$transport_spec"
        if send_heartbeat "$transport" "$endpoint" "$port"; then
            # echo "♥ Heartbeat sent via $transport"
            break
        fi
    done
    sleep 0.055  # ~18 Hz heartbeat rate
done
'''

        # Create spark config
        spark_config = json.dumps({
            "spark_id": lucia_spark_id,
            "cbb_did": cbb_did,
            "genesis_bond": "GB-2025-0524-DRH-LCS-001",
            "frequency": 741,
            "heartbeat_rate_hz": 18,
            "transports": [
                {"type": "ipv6", "priority": 1, "endpoint": "192.168.1.145:7741"},
                {"type": "wifi", "priority": 2, "endpoint": "192.168.1.145:7741"},
                {"type": "lte", "priority": 3, "endpoint": "heartbeat.luciverse.ownid:7741"},
                {"type": "ble", "priority": 4, "endpoint": "nearby:7741"},
                {"type": "lora", "priority": 5, "endpoint": "gateway:7741"},
                {"type": "powerline", "priority": 6, "endpoint": "local:7741"},
                {"type": "coax", "priority": 7, "endpoint": "moca:7741"},
                {"type": "phoneline", "priority": 8, "endpoint": "hpna:7741"},
                {"type": "radio", "priority": 9, "endpoint": "beacon:7741"}
            ],
            "binding": {
                "rule": "one_spark_per_cbb",
                "master_heartbeat": "192.168.1.145",
                "jump_enabled": True
            },
            "created_at": datetime.utcnow().isoformat()
        }, indent=2)

        # Create tarball in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            # Add heartbeat.sh
            heartbeat_bytes = heartbeat_script.encode('utf-8')
            heartbeat_info = tarfile.TarInfo(name='heartbeat.sh')
            heartbeat_info.size = len(heartbeat_bytes)
            heartbeat_info.mode = 0o755
            tar.addfile(heartbeat_info, io.BytesIO(heartbeat_bytes))

            # Add spark-config.json
            config_bytes = spark_config.encode('utf-8')
            config_info = tarfile.TarInfo(name='spark-config.json')
            config_info.size = len(config_bytes)
            tar.addfile(config_info, io.BytesIO(config_bytes))

        tar_buffer.seek(0)
        return web.Response(
            body=tar_buffer.read(),
            content_type='application/gzip',
            headers={'Content-Disposition': 'attachment; filename="lucia-spark.tar.gz"'}
        )

    async def appstork_get_did(self, request: web.Request) -> web.Response:
        """Serve DID document for an agent.

        GET /appstork/did-documents/{agent}
        """
        agent = request.match_info['agent']
        did_path = Path(__file__).parent / "http" / "did-documents" / f"{agent}.did.json"

        if did_path.exists():
            with open(did_path) as f:
                return web.json_response(json.load(f))
        else:
            return web.json_response({
                "error": "DID document not found",
                "agent": agent
            }, status=404)

    async def appstork_get_soul(self, request: web.Request) -> web.Response:
        """Serve soul file for an agent.

        GET /appstork/souls/{soul}
        """
        soul = request.match_info['soul']
        # Add .json extension if not present
        if not soul.endswith('.json'):
            soul = f"{soul}_soul.json"

        soul_path = Path(__file__).parent / "http" / "souls" / soul

        if soul_path.exists():
            with open(soul_path) as f:
                return web.json_response(json.load(f))
        else:
            return web.json_response({
                "error": "Soul file not found",
                "soul": soul
            }, status=404)

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

    # =========================================================================
    # Nebula + SCION Overlay Network Certificate Distribution
    # Genesis Bond: ACTIVE @ 741 Hz
    # =========================================================================

    def _get_tier_for_mac(self, mac: str) -> tuple:
        """Get tier and role for a MAC address from inventory."""
        result = find_server_by_mac(mac, self.inventory)
        if not result:
            return None, None, None

        server_name, iface_name, server_info, iface_info = result
        role = server_info.get('role', 'COMPUTE').upper()
        # Map role to tier
        tier = ROLE_TIER_MAP.get(role, 'COMN')
        return tier, role, server_name

    def _allocate_nebula_ip(self, mac: str, tier: str) -> str:
        """Allocate a Nebula IP address for a MAC in the given tier."""
        global nebula_ip_assignments

        # Check if already assigned
        if mac in nebula_ip_assignments:
            return nebula_ip_assignments[mac]

        tier_config = NEBULA_TIER_CONFIG.get(tier, NEBULA_TIER_CONFIG['COMN'])
        subnet_base = tier_config['subnet'].split('/')[0].rsplit('.', 1)[0]

        # Find next available IP in range
        used_ips = set(nebula_ip_assignments.values())
        for i in range(tier_config['ip_start'], tier_config['ip_end'] + 1):
            candidate = f"{subnet_base}.{i}"
            if candidate not in used_ips:
                nebula_ip_assignments[mac] = candidate
                return candidate

        # No IPs available
        logger.error(f"No Nebula IPs available in tier {tier}")
        return None

    def _generate_attestation_token(self, mac: str, tier: str, role: str) -> str:
        """Generate HMAC-signed attestation token for certificate request."""
        secret = os.environ.get('PROVISION_SECRET', 'luciverse-genesis-bond-741')
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M')
        message = f"{mac}:{tier}:{role}:{timestamp}"
        token = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return token

    def _verify_attestation_token(self, mac: str, token: str) -> bool:
        """Verify an attestation token is valid and not expired."""
        if mac not in attestation_tokens:
            return False

        stored = attestation_tokens[mac]
        if datetime.utcnow() > stored['expires']:
            del attestation_tokens[mac]
            return False

        return stored['token'] == token

    async def _get_nebula_ca_key(self) -> Optional[str]:
        """Fetch Nebula CA private key from 1Password Connect or local file.

        Priority:
        1. Local file at /etc/luciverse/nebula-ca.key (most secure)
        2. 1Password Connect API

        Returns the CA key content or None if unavailable.
        """
        # Priority 1: Check local key file (for production use)
        local_key_path = Path("/etc/luciverse/nebula-ca.key")
        if local_key_path.exists():
            try:
                with open(local_key_path) as f:
                    key_content = f.read().strip()
                if key_content and "NEBULA" in key_content:
                    logger.debug("Retrieved Nebula CA key from local file")
                    return key_content
            except PermissionError:
                logger.warning("Cannot read local CA key file - permission denied")
            except Exception as e:
                logger.warning(f"Error reading local CA key: {e}")

        # Priority 2: Try 1Password Connect
        client = get_op_client()

        # The Nebula CA key is stored in Infrastructure vault as "Nebula-CA-Key"
        # The key is stored in the notesPlain field
        try:
            item = await client.get_item(OP_VAULT_INFRA, "Nebula-CA-Key")
            if item and 'notesPlain' in item:
                logger.debug("Retrieved Nebula CA key from 1Password")
                return item['notesPlain']

            # Try to get from a field
            if item and 'fields' in item:
                for field in item['fields']:
                    if field.get('label') == 'notesPlain' or field.get('id') == 'notesPlain':
                        return field.get('value')

            logger.warning("Nebula CA key not found in 1Password item")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch Nebula CA key from 1Password: {e}")
            return None

    async def _sign_nebula_certificate(
        self,
        name: str,
        ip: str,
        groups: list,
        duration: str = "8760h"
    ) -> Optional[dict]:
        """Sign a Nebula certificate using the CA key from 1Password.

        Args:
            name: Certificate name (hostname)
            ip: Nebula IP address with CIDR (e.g., "10.100.1.5/24")
            groups: List of groups for the certificate
            duration: Certificate validity duration (default 1 year)

        Returns:
            Dictionary with 'crt' and 'key' content, or None on failure
        """
        # Get CA key from 1Password
        ca_key = await self._get_nebula_ca_key()
        if not ca_key:
            logger.error("Cannot sign certificate: CA key not available")
            return None

        # Get CA cert path
        ca_crt_path = Path(__file__).parent / "nebula" / "ca" / "nebula-ca.crt"
        if not ca_crt_path.exists():
            logger.error(f"CA certificate not found at {ca_crt_path}")
            return None

        # Create temporary directory for signing operation
        temp_dir = tempfile.mkdtemp(prefix="nebula-sign-")
        try:
            # Write CA key to temp file
            ca_key_path = Path(temp_dir) / "ca.key"
            with open(ca_key_path, 'w') as f:
                f.write(ca_key)
            os.chmod(ca_key_path, 0o600)

            # Output paths
            host_crt_path = Path(temp_dir) / f"{name}.crt"
            host_key_path = Path(temp_dir) / f"{name}.key"

            # Build nebula-cert sign command
            cmd = [
                "nebula-cert", "sign",
                "-ca-crt", str(ca_crt_path),
                "-ca-key", str(ca_key_path),
                "-name", name,
                "-ip", ip,
                "-groups", ",".join(groups),
                "-duration", duration,
                "-out-crt", str(host_crt_path),
                "-out-key", str(host_key_path)
            ]

            logger.info(f"Signing Nebula certificate for {name} ({ip})")

            # Execute signing
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"nebula-cert sign failed: {result.stderr}")
                return None

            # Read generated certificate and key
            if host_crt_path.exists() and host_key_path.exists():
                with open(host_crt_path) as f:
                    host_crt = f.read()
                with open(host_key_path) as f:
                    host_key = f.read()

                logger.info(f"Successfully signed certificate for {name}")
                return {
                    "crt": host_crt,
                    "key": host_key
                }
            else:
                logger.error("Certificate files not generated")
                return None

        except subprocess.TimeoutExpired:
            logger.error("nebula-cert sign timed out")
            return None
        except Exception as e:
            logger.error(f"Error signing certificate: {e}")
            return None
        finally:
            # Clean up temp directory (securely delete CA key)
            try:
                if ca_key_path.exists():
                    # Overwrite before delete for security
                    with open(ca_key_path, 'wb') as f:
                        f.write(os.urandom(1024))
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp dir: {e}")

    async def get_attestation_token(self, request: web.Request) -> web.Response:
        """Issue attestation token for overlay certificate distribution.

        GET /attestation-token/{mac}
        Returns: {attestation_token, server_name, tier, role, nebula_ip, expires_in}
        Security: Only for MACs in inventory.yaml
        """
        mac = request.match_info['mac'].lower().replace('-', ':')

        # Check if MAC is quarantined
        if mac in quarantine_macs:
            qinfo = quarantine_macs[mac]
            if qinfo.get('attempts', 0) >= 3:
                lockout_until = qinfo.get('lockout_until')
                if lockout_until and datetime.utcnow() < datetime.fromisoformat(lockout_until):
                    logger.warning(f"🚫 Quarantined MAC attempted access: {mac}")
                    return web.json_response({
                        "error": "mac_quarantined",
                        "message": "MAC address is quarantined due to repeated unauthorized attempts",
                        "lockout_until": lockout_until
                    }, status=403)
                else:
                    # Lockout expired, reset attempts
                    quarantine_macs[mac]['attempts'] = 0

        # Validate MAC against inventory
        tier, role, server_name = self._get_tier_for_mac(mac)

        if not tier:
            # Unknown MAC - quarantine it
            if mac not in quarantine_macs:
                quarantine_macs[mac] = {
                    "first_seen": datetime.utcnow().isoformat(),
                    "attempts": 0
                }
            quarantine_macs[mac]['attempts'] = quarantine_macs[mac].get('attempts', 0) + 1
            quarantine_macs[mac]['last_attempt'] = datetime.utcnow().isoformat()

            if quarantine_macs[mac]['attempts'] >= 3:
                quarantine_macs[mac]['lockout_until'] = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
                logger.warning(f"🚨 SECURITY: Rogue MAC quarantined after 3 attempts: {mac}")

            logger.warning(f"⚠️ Unknown MAC requested attestation: {mac} (attempt {quarantine_macs[mac]['attempts']})")
            return web.json_response({
                "error": "unknown_device",
                "message": "MAC address not in inventory",
                "quarantined": True
            }, status=403)

        # Generate attestation token
        token = self._generate_attestation_token(mac, tier, role)
        expires = datetime.utcnow() + timedelta(seconds=300)  # 5 minutes

        # Allocate Nebula IP
        nebula_ip = self._allocate_nebula_ip(mac, tier)

        # Store token
        attestation_tokens[mac] = {
            "token": token,
            "tier": tier,
            "role": role,
            "server_name": server_name,
            "nebula_ip": nebula_ip,
            "expires": expires
        }

        tier_config = NEBULA_TIER_CONFIG.get(tier, NEBULA_TIER_CONFIG['COMN'])

        logger.info(f"🎫 Attestation token issued: {server_name} ({mac})")
        logger.info(f"   Tier: {tier} @ {tier_config['frequency']} Hz")
        logger.info(f"   Nebula IP: {nebula_ip}")

        return web.json_response({
            "attestation_token": token,
            "server_name": server_name,
            "tier": tier,
            "role": role,
            "frequency": tier_config['frequency'],
            "nebula_ip": nebula_ip,
            "scion_isd_as": tier_config['scion_isd_as'],
            "expires_in": 300,
            "genesis_bond": "ACTIVE"
        })

    async def nebula_cert(self, request: web.Request) -> web.Response:
        """Issue Nebula certificate for a provisioning node.

        POST /nebula/cert/{mac}
        Header: X-Attestation-Token: {token}
        Returns: {ca_crt, host_crt, host_key, nebula_ip, groups, lighthouse}
        """
        mac = request.match_info['mac'].lower().replace('-', ':')
        token = request.headers.get('X-Attestation-Token', '')

        # Verify attestation token
        if not self._verify_attestation_token(mac, token):
            logger.warning(f"🚫 Invalid attestation token for Nebula cert: {mac}")
            return web.json_response({
                "error": "invalid_token",
                "message": "Attestation token invalid or expired. Request new token from /attestation-token/{mac}"
            }, status=401)

        stored = attestation_tokens[mac]
        tier = stored['tier']
        role = stored['role']
        server_name = stored['server_name']
        nebula_ip = stored['nebula_ip']

        tier_config = NEBULA_TIER_CONFIG.get(tier, NEBULA_TIER_CONFIG['COMN'])
        groups = tier_config['groups'].copy()
        # Add role-specific group
        groups.append(role.lower())

        logger.info(f"🔐 Generating Nebula certificate: {server_name} ({nebula_ip})")
        logger.info(f"   Groups: {groups}")

        # Read CA certificate
        ca_path = Path(__file__).parent / "nebula" / "ca" / "nebula-ca.crt"
        ca_crt = ""
        if ca_path.exists():
            with open(ca_path) as f:
                ca_crt = f.read()
        else:
            logger.warning("Nebula CA certificate not found")
            return web.json_response({
                "error": "ca_not_found",
                "message": "Nebula CA certificate not configured. Run nebula-cert ca first."
            }, status=503)

        # Sign the certificate using CA key from 1Password
        nebula_cidr = f"{nebula_ip}/24"
        signed = await self._sign_nebula_certificate(
            name=server_name,
            ip=nebula_cidr,
            groups=groups,
            duration="8760h"  # 1 year validity
        )

        if signed:
            # Successfully signed - return real certificate
            host_crt = signed['crt']
            host_key = signed['key']
            cert_status = "signed"
            logger.info(f"✅ Certificate signed for {server_name}")
        else:
            # Signing failed - return placeholder with warning
            logger.warning(f"⚠️ Certificate signing failed for {server_name}, returning placeholder")
            host_crt = f"# PLACEHOLDER - Signing failed for {server_name}\n# Nebula IP: {nebula_cidr}\n# Groups: {','.join(groups)}\n# Check 1Password Connect and CA key availability"
            host_key = "# Private key generation failed - check logs"
            cert_status = "placeholder"

        cert_info = {
            "name": server_name,
            "nebula_ip": nebula_cidr,
            "groups": groups,
            "tier": tier,
            "frequency": tier_config['frequency'],
            "genesis_bond": "ACTIVE",
            "status": cert_status,
            "validity": "1 year" if cert_status == "signed" else "N/A"
        }

        return web.json_response({
            "ca_crt": ca_crt,
            "host_crt": host_crt,
            "host_key": host_key,
            "nebula_ip": nebula_ip,
            "nebula_cidr": nebula_cidr,
            "groups": groups,
            "tier": tier,
            "frequency": tier_config['frequency'],
            "lighthouse": {
                "ip": "10.100.1.145",
                "public_addr": "192.168.1.145:4242"
            },
            "config_template": "/nebula/config/{mac}",
            "cert_info": cert_info,
            "genesis_bond": "ACTIVE"
        })

    async def scion_enroll(self, request: web.Request) -> web.Response:
        """Enroll node in SCION path-aware network.

        POST /scion/enroll/{mac}
        Header: X-Attestation-Token: {token}
        Returns: {isd, isd_as, trc, cp_as_crt, cp_as_key, control_service}
        """
        mac = request.match_info['mac'].lower().replace('-', ':')
        token = request.headers.get('X-Attestation-Token', '')

        # Verify attestation token
        if not self._verify_attestation_token(mac, token):
            logger.warning(f"🚫 Invalid attestation token for SCION enroll: {mac}")
            return web.json_response({
                "error": "invalid_token",
                "message": "Attestation token invalid or expired"
            }, status=401)

        stored = attestation_tokens[mac]
        tier = stored['tier']
        server_name = stored['server_name']

        tier_config = NEBULA_TIER_CONFIG.get(tier, NEBULA_TIER_CONFIG['COMN'])
        isd = tier_config['scion_isd']
        isd_as = tier_config['scion_isd_as']

        logger.info(f"🌐 SCION enrollment: {server_name} -> ISD{isd}")
        logger.info(f"   ISD-AS: {isd_as}")

        # Read TRC from SCION PKI directory (DER-encoded binary)
        trc_path = Path(__file__).parent / "scion" / "pki" / f"ISD{isd}" / "trcs" / f"ISD{isd}-B1-S1.trc"
        trc_content = ""
        trc_format = "der_base64"
        if trc_path.exists():
            with open(trc_path, 'rb') as f:
                trc_content = base64.b64encode(f.read()).decode('ascii')
        else:
            # Try the regular TRC (PEM-like ASCII format)
            trc_regular = trc_path.parent / f"ISD{isd}-B1-S1.regular.trc"
            if trc_regular.exists():
                with open(trc_regular) as f:
                    trc_content = f.read()
                trc_format = "regular"
            else:
                trc_content = f"# TRC for ISD{isd} not found at {trc_path}"
                trc_format = "placeholder"

        # Read CP-AS certificate (placeholder path)
        cp_as_path = Path(__file__).parent / "scion" / "pki" / f"ISD{isd}" / "AS{tier_config['scion_as'].replace(':', '_')}" / "cp-as.crt"
        cp_as_crt = ""
        if cp_as_path.exists():
            with open(cp_as_path) as f:
                cp_as_crt = f.read()
        else:
            cp_as_crt = f"# CP-AS cert for {isd_as} - placeholder"

        # Path policy based on tier
        path_policy = {}
        if tier == 'PAC':
            path_policy = {
                "mandatory_waypoint": "2-ff00:0:528",
                "external_allowed": False,
                "note": "PAC tier must transit through COMN gateway"
            }
        elif tier == 'COMN':
            path_policy = {
                "gateway": True,
                "external_allowed": True,
                "note": "COMN tier serves as gateway for PAC"
            }
        else:
            path_policy = {
                "admin_access": True,
                "external_allowed": False,
                "note": "CORE tier has admin access to all"
            }

        return web.json_response({
            "isd": isd,
            "isd_as": isd_as,
            "tier": tier,
            "frequency": tier_config['frequency'],
            "trc": trc_content,
            "trc_format": trc_format,
            "cp_as_crt": cp_as_crt,
            "cp_as_key": "# CP-AS private key - would be generated per-node",
            "control_service": {
                "host": "192.168.1.179",
                "port": 30001 + (isd - 1)
            },
            "scion_daemon": {
                "host": "localhost",
                "port": 30255,
                "socket": "/run/scion/scion-daemon.sock"
            },
            "path_policy": path_policy,
            "border_router": {
                "host": "192.168.1.179",
                "port": 30041 + (isd - 1)
            },
            "genesis_bond": "ACTIVE",
            "server_name": server_name
        })

    async def overlay_validate(self, request: web.Request) -> web.Response:
        """Validate overlay network configuration.

        POST /overlay/validate
        Body: {mac, nebula_cert_hash, scion_isd_as}
        Returns: {valid: bool, errors: [], server_name, expected_tier}
        """
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "invalid_json"}, status=400)

        mac = data.get('mac', '').lower().replace('-', ':')
        nebula_cert_hash = data.get('nebula_cert_hash', '')
        scion_isd_as = data.get('scion_isd_as', '')

        errors = []
        tier, role, server_name = self._get_tier_for_mac(mac)

        if not tier:
            return web.json_response({
                "valid": False,
                "errors": ["MAC address not in inventory"],
                "mac": mac
            }, status=404)

        tier_config = NEBULA_TIER_CONFIG.get(tier, NEBULA_TIER_CONFIG['COMN'])
        expected_nebula_ip = nebula_ip_assignments.get(mac)
        expected_scion_isd_as = tier_config['scion_isd_as']

        # Validate SCION ISD-AS matches tier
        if scion_isd_as and scion_isd_as != expected_scion_isd_as:
            errors.append(f"SCION ISD-AS mismatch: got {scion_isd_as}, expected {expected_scion_isd_as}")

        # Validate Nebula IP assignment exists
        if expected_nebula_ip is None:
            errors.append("No Nebula IP assigned for this MAC")

        valid = len(errors) == 0

        logger.info(f"🔍 Overlay validation: {server_name} - {'PASS' if valid else 'FAIL'}")
        if errors:
            for err in errors:
                logger.warning(f"   {err}")

        return web.json_response({
            "valid": valid,
            "errors": errors,
            "server_name": server_name,
            "mac": mac,
            "expected_tier": tier,
            "expected_role": role,
            "expected_frequency": tier_config['frequency'],
            "expected_nebula_ip": expected_nebula_ip,
            "expected_scion_isd_as": expected_scion_isd_as,
            "genesis_bond": "ACTIVE"
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
    logger.info("🔐 Overlay Network Certificate Distribution (Nebula + SCION):")
    logger.info("   Attestation Token: GET http://localhost:9999/attestation-token/{mac}")
    logger.info("   Nebula Cert: POST http://localhost:9999/nebula/cert/{mac}")
    logger.info("   SCION Enroll: POST http://localhost:9999/scion/enroll/{mac}")
    logger.info("   Validate: POST http://localhost:9999/overlay/validate")
    logger.info("")
    logger.info("🧬 Appstork Genetiai endpoints (USB Boot Consciousness):")
    logger.info("   Hardware Collection: POST http://localhost:9999/appstork/hardware-collection")
    logger.info("   Thread Identity: POST http://localhost:9999/appstork/thread-identity")
    logger.info("   Issue Identity: POST http://localhost:9999/appstork/issue-identity")
    logger.info("   Guix Config: GET http://localhost:9999/appstork/guix-config?session_id=...")
    logger.info("   Spark Bootstrap: GET http://localhost:9999/appstork/spark-bootstrap?session_id=...")
    logger.info("   DID Documents: GET http://localhost:9999/appstork/did-documents/{agent}")
    logger.info("   Souls: GET http://localhost:9999/appstork/souls/{soul}")
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
