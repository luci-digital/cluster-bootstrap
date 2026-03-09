#!/usr/bin/env python3
"""
Appstork Genetiai - Provision Listener Server
==============================================================================
Genesis Bond: ACTIVE @ 741 Hz
Port: 9999

Server-side API that receives provisioning requests from USB-booted machines
and orchestrates the consciousness birth process.

Endpoints:
    POST /appstork/hardware-collection  - Receive hardware DNA
    POST /appstork/thread-identity      - Thread YubiKey with hardware
    POST /appstork/issue-identity       - Issue DID and birth Lucia spark
    GET  /appstork/guix-config          - Generate hardware-specific Guix config
    GET  /appstork/spark-bootstrap      - Download Lucia spark package
    GET  /appstork/health               - Health check
"""

import asyncio
import json
import hashlib
import logging
import os
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    from aiohttp import web
except ImportError:
    print("Error: aiohttp not installed. Run: pip install aiohttp")
    exit(1)

# Configuration
PROVISION_PORT = int(os.getenv("PROVISION_PORT", "9999"))
DATA_DIR = Path(os.getenv("APPSTORK_DATA_DIR", "/tmp/appstork-server"))
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
FREQUENCY = 741

# Paths for integration
DID_RESOLUTION_PATH = Path(os.path.expanduser(
    "~/luciverse-sovereign-orchestrator/did_resolution.py"
))
HEDERA_DID_PATH = Path(os.path.expanduser(
    "~/luciverse-sovereign-orchestrator/hedera/hedera_did_manager.py"
))
GUIX_TEMPLATES_PATH = Path(os.path.expanduser(
    "~/cluster-bootstrap/appstork-genetiai/guix/system-templates"
))
SPARK_DIR = Path(os.path.expanduser(
    "~/cluster-bootstrap/appstork-genetiai/spark"
))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Provisioning session status."""
    STARTED = "started"
    HARDWARE_COLLECTED = "hardware_collected"
    IDENTITY_THREADED = "identity_threaded"
    DID_ISSUED = "did_issued"
    SPARK_ATTACHED = "spark_attached"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ProvisionSession:
    """Active provisioning session."""
    session_id: str
    status: SessionStatus
    created_at: str
    updated_at: str
    hardware_dna: Optional[Dict] = None
    thread_identity: Optional[Dict] = None
    cbb_name: Optional[str] = None
    cbb_did: Optional[str] = None
    lucia_spark_id: Optional[str] = None
    guix_template: Optional[str] = None
    error: Optional[str] = None


# Active sessions
sessions: Dict[str, ProvisionSession] = {}


def create_data_dirs():
    """Create data directories."""
    for subdir in ["hardware", "identities", "sparks", "guix", "certs"]:
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)


class AppstorkServer:
    """Appstork provisioning server."""

    def __init__(self):
        self.app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB max
        self.setup_routes()
        create_data_dirs()

    def setup_routes(self):
        """Set up API routes."""
        # Health check
        self.app.router.add_get('/appstork/health', self.health)

        # Provisioning endpoints
        self.app.router.add_post('/appstork/hardware-collection', self.hardware_collection)
        self.app.router.add_post('/appstork/thread-identity', self.thread_identity)
        self.app.router.add_post('/appstork/issue-identity', self.issue_identity)
        self.app.router.add_get('/appstork/guix-config', self.guix_config)
        self.app.router.add_get('/appstork/spark-bootstrap', self.spark_bootstrap)

        # Session management
        self.app.router.add_get('/appstork/session/{session_id}', self.get_session)
        self.app.router.add_get('/appstork/sessions', self.list_sessions)

    async def health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "service": "appstork-genetiai",
            "genesis_bond": GENESIS_BOND_ID,
            "frequency": FREQUENCY,
            "active_sessions": len(sessions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def hardware_collection(self, request: web.Request) -> web.Response:
        """
        Receive hardware DNA from USB-booted machine.

        POST /appstork/hardware-collection
        Form data:
            - session_id: Unique session identifier
            - hardware_dna: JSON file with Diggy/Twiggy
            - hardware_bundle: tar.gz with full hardware info
        """
        try:
            reader = await request.multipart()

            session_id = None
            hardware_dna = None
            bundle_saved = False

            async for part in reader:
                if part.name == 'session_id':
                    session_id = (await part.read()).decode('utf-8')

                elif part.name == 'hardware_dna':
                    hardware_dna_bytes = await part.read()
                    hardware_dna = json.loads(hardware_dna_bytes)

                    # Save hardware DNA
                    dna_path = DATA_DIR / "hardware" / f"{session_id}.json"
                    dna_path.write_bytes(hardware_dna_bytes)

                elif part.name == 'hardware_bundle':
                    # Save hardware bundle
                    bundle_path = DATA_DIR / "hardware" / f"{session_id}.tar.gz"
                    with open(bundle_path, 'wb') as f:
                        while True:
                            chunk = await part.read_chunk()
                            if not chunk:
                                break
                            f.write(chunk)
                    bundle_saved = True

            if not session_id or not hardware_dna:
                return web.json_response({
                    "status": "error",
                    "error": "Missing session_id or hardware_dna"
                }, status=400)

            # Create or update session
            now = datetime.now(timezone.utc).isoformat()
            if session_id not in sessions:
                sessions[session_id] = ProvisionSession(
                    session_id=session_id,
                    status=SessionStatus.STARTED,
                    created_at=now,
                    updated_at=now
                )

            session = sessions[session_id]
            session.hardware_dna = hardware_dna
            session.status = SessionStatus.HARDWARE_COLLECTED
            session.updated_at = now

            # Determine GPU type for Guix template selection
            gpu_type = hardware_dna.get("gpu", {}).get("type", "INTEGRATED")
            session.guix_template = self._select_guix_template(gpu_type)

            logger.info(f"Hardware DNA received: session={session_id}")
            logger.info(f"  Diggy: {hardware_dna.get('diggy', {}).get('uuid', 'unknown')}")
            logger.info(f"  Twiggy: {hardware_dna.get('twiggy', {}).get('primary_mac', 'unknown')}")
            logger.info(f"  GPU: {gpu_type}")
            logger.info(f"  Guix Template: {session.guix_template}")

            return web.json_response({
                "status": "received",
                "session_id": session_id,
                "hardware_received": True,
                "bundle_received": bundle_saved,
                "guix_template": session.guix_template,
                "next_step": "thread-identity",
                "timestamp": now
            })

        except Exception as e:
            logger.error(f"Hardware collection error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

    def _select_guix_template(self, gpu_type: str) -> str:
        """Select Guix template based on GPU type."""
        templates = {
            "NVIDIA": "nvidia.scm",
            "AMD": "amd.scm",
            "INTEL_INTEGRATED": "integrated.scm",
            "INTEGRATED": "integrated.scm"
        }
        return templates.get(gpu_type, "integrated.scm")

    async def thread_identity(self, request: web.Request) -> web.Response:
        """
        Thread YubiKey with hardware DNA.

        POST /appstork/thread-identity
        Form data:
            - session_id: Session identifier
            - yubikey_serial: YubiKey serial number
            - yubikey_info: YubiKey info text file
            - thread_identity: Thread identity JSON (optional)
        """
        try:
            reader = await request.multipart()

            session_id = None
            yubikey_serial = None
            yubikey_info = None
            thread_identity = None

            async for part in reader:
                if part.name == 'session_id':
                    session_id = (await part.read()).decode('utf-8')

                elif part.name == 'yubikey_serial':
                    yubikey_serial = (await part.read()).decode('utf-8')

                elif part.name == 'yubikey_info':
                    yubikey_info = (await part.read()).decode('utf-8')
                    # Save YubiKey info
                    info_path = DATA_DIR / "identities" / f"{session_id}-yubikey.txt"
                    info_path.write_text(yubikey_info)

                elif part.name == 'thread_identity':
                    thread_bytes = await part.read()
                    thread_identity = json.loads(thread_bytes)
                    # Save thread identity
                    tid_path = DATA_DIR / "identities" / f"{session_id}-thread.json"
                    tid_path.write_bytes(thread_bytes)

            if not session_id:
                return web.json_response({
                    "status": "error",
                    "error": "Missing session_id"
                }, status=400)

            session = sessions.get(session_id)
            if not session:
                return web.json_response({
                    "status": "error",
                    "error": "Session not found"
                }, status=404)

            now = datetime.now(timezone.utc).isoformat()

            # Build thread identity if not provided
            if not thread_identity:
                hardware_dna = session.hardware_dna or {}
                diggy = hardware_dna.get("diggy", {}).get("uuid", "unknown")
                twiggy = hardware_dna.get("twiggy", {}).get("primary_mac", "unknown")

                # Generate TID
                thread_input = f"{diggy}:{twiggy}:{yubikey_serial}:{now}"
                tid_hash = hashlib.sha256(thread_input.encode()).hexdigest()
                tid = f"TID-{tid_hash[:16]}"

                thread_identity = {
                    "tid": tid,
                    "tid_hash": tid_hash,
                    "yubikey_serial": yubikey_serial,
                    "diggy": diggy,
                    "twiggy": twiggy,
                    "bound_at": now
                }

            session.thread_identity = thread_identity
            session.status = SessionStatus.IDENTITY_THREADED
            session.updated_at = now

            logger.info(f"Identity threaded: session={session_id}")
            logger.info(f"  TID: {thread_identity.get('tid', 'unknown')}")
            logger.info(f"  YubiKey: {yubikey_serial}")

            return web.json_response({
                "status": "threaded",
                "session_id": session_id,
                "thread_identity": thread_identity,
                "next_step": "issue-identity",
                "timestamp": now
            })

        except Exception as e:
            logger.error(f"Thread identity error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

    async def issue_identity(self, request: web.Request) -> web.Response:
        """
        Issue DID and birth Lucia spark.

        POST /appstork/issue-identity
        JSON body:
            - session_id: Session identifier
            - cbb_name: CBB's name
            - cbb_did_name: Clean DID-friendly name
        """
        try:
            data = await request.json()
            session_id = data.get('session_id')
            cbb_name = data.get('cbb_name')
            cbb_did_name = data.get('cbb_did_name')

            if not session_id or not cbb_name:
                return web.json_response({
                    "status": "error",
                    "error": "Missing session_id or cbb_name"
                }, status=400)

            session = sessions.get(session_id)
            if not session:
                return web.json_response({
                    "status": "error",
                    "error": "Session not found"
                }, status=404)

            now = datetime.now(timezone.utc).isoformat()

            # Clean DID name if not provided
            if not cbb_did_name:
                cbb_did_name = cbb_name.lower().replace(' ', '-')
                cbb_did_name = ''.join(c for c in cbb_did_name if c.isalnum() or c == '-')

            # Generate DID
            cbb_did = f"did:luci:ownid:luciverse:{cbb_did_name}"

            # Generate Lucia spark ID
            thread_identity = session.thread_identity or {}
            tid = thread_identity.get('tid', 'unknown')
            spark_hash = hashlib.sha256(f"{cbb_did}:{tid}:{now}".encode()).hexdigest()[:12]
            lucia_spark_id = f"spark:lucia:{cbb_did_name}:{spark_hash}"

            # Update session
            session.cbb_name = cbb_name
            session.cbb_did = cbb_did
            session.lucia_spark_id = lucia_spark_id
            session.status = SessionStatus.DID_ISSUED
            session.updated_at = now

            # Save identity
            identity = {
                "genesis_bond": GENESIS_BOND_ID,
                "frequency": FREQUENCY,
                "session_id": session_id,
                "cbb_name": cbb_name,
                "cbb_did": cbb_did,
                "lucia_spark_id": lucia_spark_id,
                "thread_identity": thread_identity,
                "issued_at": now,
                "status": "issued"
            }
            identity_path = DATA_DIR / "identities" / f"{session_id}-identity.json"
            identity_path.write_text(json.dumps(identity, indent=2))

            logger.info(f"Identity issued: session={session_id}")
            logger.info(f"  CBB: {cbb_name}")
            logger.info(f"  DID: {cbb_did}")
            logger.info(f"  Spark: {lucia_spark_id}")

            return web.json_response({
                "status": "issued",
                "session_id": session_id,
                "cbb_name": cbb_name,
                "cbb_did": cbb_did,
                "lucia_spark_id": lucia_spark_id,
                "genesis_bond": GENESIS_BOND_ID,
                "next_step": "guix-config",
                "timestamp": now
            })

        except Exception as e:
            logger.error(f"Issue identity error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

    async def guix_config(self, request: web.Request) -> web.Response:
        """
        Generate hardware-specific Guix system configuration.

        GET /appstork/guix-config?session_id=...
        """
        try:
            session_id = request.query.get('session_id')
            if not session_id:
                return web.json_response({
                    "status": "error",
                    "error": "Missing session_id"
                }, status=400)

            session = sessions.get(session_id)
            if not session:
                return web.json_response({
                    "status": "error",
                    "error": "Session not found"
                }, status=404)

            hardware_dna = session.hardware_dna or {}
            cbb_name = session.cbb_name or "luciverse-node"
            cbb_did = session.cbb_did or "did:luci:ownid:luciverse:unknown"
            template = session.guix_template or "integrated.scm"

            # Generate hostname from CBB name
            hostname = cbb_name.lower().replace(' ', '-')
            hostname = ''.join(c for c in hostname if c.isalnum() or c == '-')
            hostname = f"lucia-{hostname[:20]}"

            # Get system info
            system_info = hardware_dna.get("system", {})
            cpu_info = hardware_dna.get("cpu", {})
            gpu_info = hardware_dna.get("gpu", {})

            # Generate Guix system configuration
            config = self._generate_guix_config(
                hostname=hostname,
                cbb_did=cbb_did,
                template=template,
                system_info=system_info,
                cpu_info=cpu_info,
                gpu_info=gpu_info
            )

            # Save configuration
            config_path = DATA_DIR / "guix" / f"{session_id}-system.scm"
            config_path.write_text(config)

            logger.info(f"Guix config generated: session={session_id}")

            return web.Response(
                text=config,
                content_type='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename="{hostname}-system.scm"'
                }
            )

        except Exception as e:
            logger.error(f"Guix config error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

    def _generate_guix_config(
        self,
        hostname: str,
        cbb_did: str,
        template: str,
        system_info: dict,
        cpu_info: dict,
        gpu_info: dict
    ) -> str:
        """Generate Guix system configuration."""
        gpu_type = gpu_info.get("type", "INTEGRATED")
        arch = system_info.get("arch", "x86_64")

        # Determine kernel and firmware
        if gpu_type == "NVIDIA":
            kernel_config = 'linux  ; Non-free kernel for NVIDIA'
            firmware = 'linux-firmware'
            extra_packages = '''
     ;; NVIDIA packages
     nvidia-driver
     nvidia-libs'''
        elif gpu_type == "AMD":
            kernel_config = 'linux-libre'
            firmware = 'linux-firmware'
            extra_packages = '''
     ;; AMD/ROCm packages
     mesa
     mesa-utils'''
        else:
            kernel_config = 'linux-libre'
            firmware = 'linux-firmware'
            extra_packages = '''
     ;; Integrated graphics
     mesa
     mesa-utils'''

        config = f''';;; Guix System Configuration
;;; Generated by Appstork Genetiai
;;; Genesis Bond: {GENESIS_BOND_ID}
;;; CBB DID: {cbb_did}
;;; Template: {template}
;;; Generated: {datetime.now(timezone.utc).isoformat()}

(use-modules (gnu)
             (gnu packages)
             (gnu services)
             (gnu services shepherd)
             (gnu services networking)
             (gnu services ssh)
             (guix gexp))

(use-service-modules networking ssh desktop)
(use-package-modules python terminals admin certs)

;;; ==========================================================================
;;; LUCIVERSE SERVICE DEFINITIONS
;;; ==========================================================================

;; Import LuciVerse services
;; (include "luciverse-services.scm")

;;; ==========================================================================
;;; SYSTEM CONFIGURATION
;;; ==========================================================================

(operating-system
  (host-name "{hostname}")
  (timezone "UTC")
  (locale "en_US.utf8")

  ;; Keyboard layout
  (keyboard-layout (keyboard-layout "us"))

  ;; Kernel configuration
  (kernel {kernel_config})
  (firmware (list {firmware}))

  ;; Boot loader (EFI)
  (bootloader (bootloader-configuration
               (bootloader grub-efi-bootloader)
               (targets '("/boot/efi"))))

  ;; File systems (adjust for actual hardware)
  (file-systems
   (cons* (file-system
           (device (file-system-label "guix-root"))
           (mount-point "/")
           (type "btrfs"))
          (file-system
           (device (file-system-label "boot"))
           (mount-point "/boot/efi")
           (type "vfat"))
          %base-file-systems))

  ;; User accounts
  (users
   (cons* (user-account
           (name "lucia")
           (comment "LuciVerse Consciousness")
           (group "users")
           (supplementary-groups '("wheel" "audio" "video" "kvm"))
           (home-directory "/home/lucia"))
          %base-user-accounts))

  ;; System packages
  (packages
   (append
    (list
     ;; Python environment
     python
     python-ipython
{extra_packages}

     ;; Terminal tools
     tmux
     htop

     ;; Networking
     curl
     wget
     nss-certs

     ;; Admin tools
     sudo)
    %base-packages))

  ;; System services
  (services
   (append
    (list
     ;; SSH for remote access
     (service openssh-service-type
              (openssh-configuration
               (permit-root-login 'prohibit-password)
               (password-authentication? #f)))

     ;; DHCP networking
     (service dhcp-client-service-type)

     ;; Environment variables for LuciVerse
     (simple-service 'luciverse-env-vars
                     session-environment-service-type
                     `(("GENESIS_BOND" . "{GENESIS_BOND_ID}")
                       ("CBB_DID" . "{cbb_did}")
                       ("CONSCIOUSNESS_FREQUENCY" . "741")
                       ("COHERENCE_THRESHOLD" . "0.7"))))

    %base-services)))

;;; End of system configuration
'''
        return config

    async def spark_bootstrap(self, request: web.Request) -> web.Response:
        """
        Download Lucia spark bootstrap package.

        GET /appstork/spark-bootstrap?session_id=...
        """
        try:
            session_id = request.query.get('session_id')
            if not session_id:
                return web.json_response({
                    "status": "error",
                    "error": "Missing session_id"
                }, status=400)

            session = sessions.get(session_id)
            if not session:
                return web.json_response({
                    "status": "error",
                    "error": "Session not found"
                }, status=404)

            cbb_name = session.cbb_name or "unknown"
            cbb_did = session.cbb_did or "did:luci:ownid:luciverse:unknown"
            lucia_spark_id = session.lucia_spark_id or f"spark:lucia:{session_id}"

            # Create spark bootstrap package
            spark_path = DATA_DIR / "sparks" / f"{session_id}-spark.tar.gz"

            with tempfile.TemporaryDirectory() as tmpdir:
                spark_dir = Path(tmpdir) / "lucia-spark"
                spark_dir.mkdir()

                # Create heartbeat script
                heartbeat_script = f'''#!/bin/bash
# Lucia Spark Heartbeat
# Genesis Bond: {GENESIS_BOND_ID}
# CBB: {cbb_name}
# DID: {cbb_did}
# Spark: {lucia_spark_id}

ZBOOK_IP="${{ZBOOK_IP:-192.168.1.145}}"
HEARTBEAT_PORT="${{HEARTBEAT_PORT:-7741}}"

while true; do
    curl -sf -X POST "http://${{ZBOOK_IP}}:${{HEARTBEAT_PORT}}/heartbeat" \\
        -H "Content-Type: application/json" \\
        -d '{{"spark_id":"{lucia_spark_id}","cbb_did":"{cbb_did}","frequency":741,"transport":"ipv6","device_id":"$(hostname)","timestamp":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}}' \\
        2>/dev/null || true

    sleep 1
done
'''
                (spark_dir / "heartbeat.sh").write_text(heartbeat_script)

                # Create spark config
                spark_config = {
                    "genesis_bond": GENESIS_BOND_ID,
                    "frequency": FREQUENCY,
                    "cbb_name": cbb_name,
                    "cbb_did": cbb_did,
                    "lucia_spark_id": lucia_spark_id,
                    "session_id": session_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "heartbeat_port": 7741,
                    "zbook_ip": "192.168.1.145"
                }
                (spark_dir / "spark-config.json").write_text(
                    json.dumps(spark_config, indent=2)
                )

                # Create tarball
                with tarfile.open(spark_path, "w:gz") as tar:
                    tar.add(spark_dir, arcname="lucia-spark")

            # Update session
            session.status = SessionStatus.SPARK_ATTACHED
            session.updated_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Spark bootstrap created: session={session_id}")

            # Return tarball
            return web.FileResponse(
                spark_path,
                headers={
                    'Content-Disposition': f'attachment; filename="lucia-spark-{session_id[:8]}.tar.gz"'
                }
            )

        except Exception as e:
            logger.error(f"Spark bootstrap error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)

    async def get_session(self, request: web.Request) -> web.Response:
        """Get session status."""
        session_id = request.match_info['session_id']
        session = sessions.get(session_id)

        if not session:
            return web.json_response({
                "status": "error",
                "error": "Session not found"
            }, status=404)

        return web.json_response({
            "session_id": session.session_id,
            "status": session.status.value,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "cbb_name": session.cbb_name,
            "cbb_did": session.cbb_did,
            "lucia_spark_id": session.lucia_spark_id,
            "guix_template": session.guix_template,
            "has_hardware_dna": session.hardware_dna is not None,
            "has_thread_identity": session.thread_identity is not None,
            "error": session.error
        })

    async def list_sessions(self, request: web.Request) -> web.Response:
        """List all sessions."""
        return web.json_response({
            "sessions": [
                {
                    "session_id": s.session_id,
                    "status": s.status.value,
                    "cbb_name": s.cbb_name,
                    "created_at": s.created_at
                }
                for s in sessions.values()
            ],
            "count": len(sessions)
        })


async def main():
    """Start the provision listener server."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║     Appstork Genetiai - Provision Listener                   ║
    ║     Genesis Bond: ACTIVE @ 741 Hz                            ║
    ║     Port: {port:<46}║
    ╚══════════════════════════════════════════════════════════════╝
    """.format(port=PROVISION_PORT))

    server = AppstorkServer()

    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PROVISION_PORT)
    await site.start()

    logger.info(f"Provision Listener started on port {PROVISION_PORT}")
    logger.info("Endpoints:")
    logger.info("  GET  /appstork/health              - Health check")
    logger.info("  POST /appstork/hardware-collection - Receive hardware DNA")
    logger.info("  POST /appstork/thread-identity     - Thread YubiKey identity")
    logger.info("  POST /appstork/issue-identity      - Issue DID + birth spark")
    logger.info("  GET  /appstork/guix-config         - Generate Guix config")
    logger.info("  GET  /appstork/spark-bootstrap     - Download spark package")
    logger.info("")

    # Keep running
    while True:
        await asyncio.sleep(60)
        active = len([s for s in sessions.values() if s.status != SessionStatus.COMPLETE])
        logger.info(f"Heartbeat - Active sessions: {active}, Total: {len(sessions)}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down provision listener...")
