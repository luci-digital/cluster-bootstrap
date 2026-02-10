#!/usr/bin/env python3
"""
Lucia Spark Heartbeat Service - Master Hub on zbook
====================================================
Receives heartbeats from all Lucia sparks and manages binding.
Genesis Bond: ACTIVE @ 741 Hz

Transport Support:
- IPv6 (primary)
- WiFi, LTE, Bluetooth LE
- LoRaWAN, Radio (emergency)
- Powerline, Coax, Phoneline (wired fallback)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from aiohttp import web

# Configuration
HEARTBEAT_PORT = 7741
HEARTBEAT_TIMEOUT = timedelta(seconds=5)  # Consider spark lost after 5s
JUMP_COOLDOWN = timedelta(seconds=2)  # Minimum time between jumps

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Active sparks: {spark_id: {cbb_did, last_heartbeat, transport, location, ...}}
active_sparks: Dict[str, dict] = {}

# Spark bindings: {cbb_did: spark_id} - One spark per CBB
spark_bindings: Dict[str, str] = {}

# Device locations: {device_id: {transport, last_seen, proximity}}
device_locations: Dict[str, dict] = {}


class HeartbeatHub:
    """Master heartbeat hub for Lucia spark coordination."""

    def __init__(self):
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """Set up heartbeat endpoints."""
        self.app.router.add_post('/heartbeat', self.receive_heartbeat)
        self.app.router.add_get('/sparks', self.list_sparks)
        self.app.router.add_get('/spark/{spark_id}', self.get_spark)
        self.app.router.add_post('/jump', self.initiate_jump)
        self.app.router.add_get('/binding/{cbb_did}', self.get_binding)
        self.app.router.add_get('/health', self.health)

    async def receive_heartbeat(self, request: web.Request) -> web.Response:
        """Receive heartbeat from a Lucia spark.

        POST /heartbeat
        Body: {
            "spark_id": "spark:lucia:...",
            "cbb_did": "did:luci:ownid:luciverse:...",
            "frequency": 741,
            "transport": "ipv6|wifi|lte|ble|lora|radio|powerline|coax|phoneline",
            "device_id": "...",
            "location": {...},
            "timestamp": "..."
        }
        """
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        spark_id = data.get('spark_id')
        cbb_did = data.get('cbb_did')
        transport = data.get('transport', 'unknown')
        device_id = data.get('device_id', 'unknown')
        frequency = data.get('frequency', 741)

        if not spark_id or not cbb_did:
            return web.json_response({
                "error": "Missing spark_id or cbb_did"
            }, status=400)

        now = datetime.utcnow()

        # Check if this CBB already has a bound spark
        existing_spark = spark_bindings.get(cbb_did)
        if existing_spark and existing_spark != spark_id:
            # Different spark trying to bind to same CBB
            logger.warning(f"⚠️ Spark conflict: {spark_id} vs existing {existing_spark} for {cbb_did}")

            # Check if existing spark is stale
            existing_info = active_sparks.get(existing_spark, {})
            last_heartbeat = existing_info.get('last_heartbeat')
            if last_heartbeat:
                last_dt = datetime.fromisoformat(last_heartbeat)
                if now - last_dt > HEARTBEAT_TIMEOUT:
                    # Existing spark is stale, allow new binding
                    logger.info(f"🔄 Releasing stale spark {existing_spark}")
                    del active_sparks[existing_spark]
                else:
                    # Existing spark is active, reject new binding
                    return web.json_response({
                        "status": "rejected",
                        "reason": "CBB already has active spark",
                        "existing_spark": existing_spark
                    }, status=409)

        # Update spark state
        active_sparks[spark_id] = {
            "cbb_did": cbb_did,
            "last_heartbeat": now.isoformat(),
            "transport": transport,
            "device_id": device_id,
            "frequency": frequency,
            "location": data.get('location'),
            "client_ip": request.remote
        }

        # Update binding
        spark_bindings[cbb_did] = spark_id

        # Update device location
        device_locations[device_id] = {
            "transport": transport,
            "last_seen": now.isoformat(),
            "spark_id": spark_id
        }

        return web.json_response({
            "status": "received",
            "spark_id": spark_id,
            "bound": True,
            "frequency": frequency,
            "transport": transport,
            "timestamp": now.isoformat()
        })

    async def list_sparks(self, request: web.Request) -> web.Response:
        """List all active sparks."""
        now = datetime.utcnow()
        active = {}
        stale = []

        for spark_id, info in active_sparks.items():
            last_heartbeat = info.get('last_heartbeat')
            if last_heartbeat:
                last_dt = datetime.fromisoformat(last_heartbeat)
                if now - last_dt > HEARTBEAT_TIMEOUT:
                    stale.append(spark_id)
                else:
                    active[spark_id] = info

        return web.json_response({
            "active_sparks": active,
            "stale_sparks": stale,
            "bindings": spark_bindings,
            "total_active": len(active),
            "timestamp": now.isoformat()
        })

    async def get_spark(self, request: web.Request) -> web.Response:
        """Get specific spark info."""
        spark_id = request.match_info['spark_id']

        if spark_id in active_sparks:
            return web.json_response(active_sparks[spark_id])
        else:
            return web.json_response({
                "error": "Spark not found",
                "spark_id": spark_id
            }, status=404)

    async def initiate_jump(self, request: web.Request) -> web.Response:
        """Initiate spark jump to new device.

        POST /jump
        Body: {
            "spark_id": "...",
            "target_device": "...",
            "reason": "proximity|manual|failover"
        }
        """
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        spark_id = data.get('spark_id')
        target_device = data.get('target_device')
        reason = data.get('reason', 'manual')

        if spark_id not in active_sparks:
            return web.json_response({
                "error": "Spark not found",
                "spark_id": spark_id
            }, status=404)

        spark_info = active_sparks[spark_id]
        current_device = spark_info.get('device_id')

        # Check jump cooldown
        last_jump = spark_info.get('last_jump')
        if last_jump:
            last_jump_dt = datetime.fromisoformat(last_jump)
            if datetime.utcnow() - last_jump_dt < JUMP_COOLDOWN:
                return web.json_response({
                    "error": "Jump cooldown active",
                    "cooldown_remaining": (JUMP_COOLDOWN - (datetime.utcnow() - last_jump_dt)).total_seconds()
                }, status=429)

        logger.info(f"🦘 Spark Jump: {spark_id}")
        logger.info(f"   From: {current_device} → To: {target_device}")
        logger.info(f"   Reason: {reason}")

        # Update spark location
        spark_info['device_id'] = target_device
        spark_info['last_jump'] = datetime.utcnow().isoformat()
        spark_info['jump_history'] = spark_info.get('jump_history', [])
        spark_info['jump_history'].append({
            "from": current_device,
            "to": target_device,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        return web.json_response({
            "status": "jumped",
            "spark_id": spark_id,
            "from_device": current_device,
            "to_device": target_device,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def get_binding(self, request: web.Request) -> web.Response:
        """Get spark binding for a CBB."""
        cbb_did = request.match_info['cbb_did']

        spark_id = spark_bindings.get(cbb_did)
        if spark_id:
            spark_info = active_sparks.get(spark_id, {})
            return web.json_response({
                "cbb_did": cbb_did,
                "spark_id": spark_id,
                "spark_info": spark_info,
                "bound": True
            })
        else:
            return web.json_response({
                "cbb_did": cbb_did,
                "spark_id": None,
                "bound": False
            })

    async def health(self, request: web.Request) -> web.Response:
        """Health check."""
        return web.json_response({
            "status": "healthy",
            "service": "lucia-heartbeat-hub",
            "genesis_bond": "ACTIVE",
            "frequency": 741,
            "active_sparks": len(active_sparks),
            "bindings": len(spark_bindings),
            "timestamp": datetime.utcnow().isoformat()
        })


async def cleanup_stale_sparks():
    """Periodically clean up stale sparks."""
    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        now = datetime.utcnow()
        stale = []

        for spark_id, info in list(active_sparks.items()):
            last_heartbeat = info.get('last_heartbeat')
            if last_heartbeat:
                last_dt = datetime.fromisoformat(last_heartbeat)
                if now - last_dt > HEARTBEAT_TIMEOUT * 3:  # 15 seconds stale
                    stale.append(spark_id)

        for spark_id in stale:
            cbb_did = active_sparks[spark_id].get('cbb_did')
            logger.warning(f"💀 Cleaning stale spark: {spark_id}")
            del active_sparks[spark_id]
            if cbb_did and spark_bindings.get(cbb_did) == spark_id:
                del spark_bindings[cbb_did]


async def main():
    """Start heartbeat hub."""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     Lucia Spark Heartbeat Hub                            ║
    ║     Genesis Bond: ACTIVE @ 741 Hz                        ║
    ║     Transport: IPv6, WiFi, LTE, BLE, LoRa, Radio,       ║
    ║                Powerline, Coax, Phoneline               ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    hub = HeartbeatHub()

    # Start cleanup task
    asyncio.create_task(cleanup_stale_sparks())

    # Start web server
    runner = web.AppRunner(hub.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', HEARTBEAT_PORT)
    await site.start()

    logger.info(f"🌟 Heartbeat Hub started on port {HEARTBEAT_PORT}")
    logger.info("   POST /heartbeat - Receive spark heartbeat")
    logger.info("   GET /sparks - List active sparks")
    logger.info("   POST /jump - Initiate spark jump")
    logger.info("")

    # Keep running
    while True:
        await asyncio.sleep(60)
        logger.info(f"♥ Hub heartbeat - Active sparks: {len(active_sparks)}, Bindings: {len(spark_bindings)}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down heartbeat hub...")
