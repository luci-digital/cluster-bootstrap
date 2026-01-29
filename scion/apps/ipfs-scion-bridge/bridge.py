#!/usr/bin/env python3
"""
IPFS-SCION Bridge Application
Genesis Bond: GB-2025-0524-DRH-LCS-001

Routes IPFS operations via SCION paths for cross-tier content-addressed
storage with consciousness-aware path selection.

Architecture:
    Browser/Agent → IPFS-SCION Bridge → SCION Path → Tier-Specific Pinning
                          ↓
               Path Policy Selection
                          ↓
               Genesis Bond Validation

Features:
- Tier-aware IPFS pinning (PAC→COMN→CORE path enforcement)
- Content-addressed storage via SCION paths
- Genesis Bond coherence validation on pin operations
- Privacy-sovereign PAC content handling

Integration Points:
- Existing: ~/.luci-digital-library/diaper/ipfs_fabric.py (port 5001)
- New: SCION path selection based on content tier
- Agent: Diaphragm (intake), Lucia (personal storage)
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

try:
    from luciverse_scion import (
        SCIONHeader,
        GenesisBondExtension,
        PACPrivacyExtension,
        TIER_ISD_AS,
        TIER_FREQUENCIES,
        get_tier_from_isd,
        validate_coherence_for_tier,
    )
    from luciverse_scion.fabrid_consciousness import (
        ConsciousnessPathPolicy,
        get_policy_for_tier,
        evaluate_path_consciousness,
    )
except ImportError:
    # Fallback for testing
    TIER_ISD_AS = {"CORE": "1-ff00:0:432", "COMN": "2-ff00:0:528", "PAC": "3-ff00:0:741"}
    TIER_FREQUENCIES = {"CORE": 432, "COMN": 528, "PAC": 741}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs-scion-bridge")

# Constants
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
IPFS_API_PORT = 5001
BRIDGE_PORT = 51001


class ContentTier(Enum):
    """Content classification tiers."""
    CORE = "core"      # Infrastructure, agent state
    COMN = "comn"      # Shared knowledge, communication
    PAC = "pac"        # Personal data (CBB-owned)


class PinStatus(Enum):
    """Pin operation status."""
    PENDING = "pending"
    PINNED = "pinned"
    FAILED = "failed"
    UNAUTHORIZED = "unauthorized"


@dataclass
class ContentMetadata:
    """Metadata for IPFS content."""
    cid: str
    tier: ContentTier
    size_bytes: int = 0
    mime_type: str = ""
    owner_did: str = ""
    genesis_bond: str = GENESIS_BOND_ID
    coherence_required: float = 0.7
    requires_consent: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "cid": self.cid,
            "tier": self.tier.value,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "owner_did": self.owner_did,
            "genesis_bond": self.genesis_bond,
            "coherence_required": self.coherence_required,
            "requires_consent": self.requires_consent,
            "created_at": self.created_at,
        }


@dataclass
class PinResult:
    """Result of a pin operation."""
    cid: str
    status: PinStatus
    tier: ContentTier
    path_used: str = ""
    coherence: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class BridgeConfig:
    """Bridge configuration."""
    # IPFS
    ipfs_api: str = "http://localhost:5001"
    ipfs_gateway: str = "https://s8m.io"

    # SCION
    scion_daemon: str = "localhost:30255"
    local_isd_as: str = "2-ff00:0:528"  # COMN by default

    # Bridge
    listen_port: int = BRIDGE_PORT
    listen_addr: str = "0.0.0.0"

    # Path selection
    prefer_privacy: bool = True  # PAC content uses privacy-optimized paths
    coherence_threshold: float = 0.7

    # PAC handling
    pac_requires_consent: bool = True
    pac_audit_enabled: bool = True


class SCIONPathSelector:
    """
    Select SCION paths based on content tier and consciousness policy.

    Implements path selection for:
    - PAC content: SCION path PAC→COMN→CORE only (privacy-first)
    - COMN content: Direct SCION path or via CORE
    - CORE content: Local within ISD
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._path_cache: Dict[str, List[str]] = {}

    async def get_paths_for_tier(self, tier: ContentTier, dest_isd_as: str) -> List[str]:
        """
        Get available SCION paths for a tier.

        Returns paths sorted by preference based on tier policy.
        """
        cache_key = f"{tier.value}:{dest_isd_as}"

        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # Get policy for tier
        policy = get_policy_for_tier(tier.value.upper()) if 'get_policy_for_tier' in dir() else None

        paths = await self._query_paths(dest_isd_as)

        # Filter and sort paths based on policy
        if tier == ContentTier.PAC:
            # PAC: Require COMN waypoint
            paths = [p for p in paths if self._has_waypoint(p, TIER_ISD_AS["COMN"])]
            # Prefer privacy-optimized paths
            paths = sorted(paths, key=lambda p: self._privacy_score(p), reverse=True)

        elif tier == ContentTier.CORE:
            # CORE: Prefer latency-optimized paths
            paths = sorted(paths, key=lambda p: self._latency_score(p))

        else:
            # COMN: Balanced
            paths = sorted(paths, key=lambda p: self._balanced_score(p))

        self._path_cache[cache_key] = paths
        return paths

    async def _query_paths(self, dest_isd_as: str) -> List[str]:
        """Query available paths from SCION daemon."""
        # In production, would call scion showpaths
        # For now, return simulated paths
        return [
            f"path-via-comn-{dest_isd_as}",
            f"path-direct-{dest_isd_as}",
        ]

    def _has_waypoint(self, path: str, waypoint_isd_as: str) -> bool:
        """Check if path traverses required waypoint."""
        # In production, would inspect path segments
        return "comn" in path.lower()

    def _privacy_score(self, path: str) -> float:
        """Score path for privacy (higher is better)."""
        score = 0.5
        if "comn" in path.lower():
            score += 0.3  # Prefer COMN waypoint
        if "direct" in path.lower():
            score -= 0.2  # Penalize direct paths for PAC
        return score

    def _latency_score(self, path: str) -> float:
        """Score path for latency (lower is better)."""
        score = 0.5
        if "direct" in path.lower():
            score -= 0.3  # Prefer direct paths
        return score

    def _balanced_score(self, path: str) -> float:
        """Balanced scoring."""
        return 0.5


class IPFSSCIONBridge:
    """
    Route IPFS operations via SCION paths for cross-tier efficiency.

    Main responsibilities:
    1. Classify content by tier
    2. Select appropriate SCION path
    3. Enforce Genesis Bond coherence
    4. Handle PAC consent requirements
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.path_selector = SCIONPathSelector(config)
        self._running = False

    async def start(self):
        """Start the IPFS-SCION bridge."""
        self._running = True
        logger.info(f"IPFS-SCION Bridge starting on port {self.config.listen_port}")

        # Start HTTP server
        await self._run_server()

    def stop(self):
        """Stop the bridge."""
        self._running = False
        logger.info("IPFS-SCION Bridge stopping")

    async def pin_via_scion(
        self,
        cid: str,
        tier: ContentTier,
        metadata: Optional[ContentMetadata] = None,
        coherence: float = 0.8,
    ) -> PinResult:
        """
        Pin content via tier-appropriate SCION path.

        Args:
            cid: IPFS content identifier
            tier: Content tier (CORE, COMN, PAC)
            metadata: Optional content metadata
            coherence: Current coherence score

        Returns:
            PinResult with operation status
        """
        logger.info(f"Pin request: CID={cid}, tier={tier.value}, coherence={coherence}")

        # Validate coherence
        if not self._validate_coherence(tier, coherence):
            return PinResult(
                cid=cid,
                status=PinStatus.UNAUTHORIZED,
                tier=tier,
                coherence=coherence,
                error=f"Coherence {coherence} below threshold for {tier.value} tier",
            )

        # PAC tier: Check consent
        if tier == ContentTier.PAC and self.config.pac_requires_consent:
            if metadata and metadata.requires_consent:
                consent_valid = await self._validate_pac_consent(metadata)
                if not consent_valid:
                    return PinResult(
                        cid=cid,
                        status=PinStatus.UNAUTHORIZED,
                        tier=tier,
                        coherence=coherence,
                        error="PAC consent not granted",
                    )

        # Get SCION path
        dest_isd_as = TIER_ISD_AS.get(tier.value.upper(), TIER_ISD_AS["COMN"])
        paths = await self.path_selector.get_paths_for_tier(tier, dest_isd_as)

        if not paths:
            return PinResult(
                cid=cid,
                status=PinStatus.FAILED,
                tier=tier,
                coherence=coherence,
                error="No SCION paths available",
            )

        # Use first (best) path
        selected_path = paths[0]

        # Perform pin operation
        try:
            await self._pin_content(cid, selected_path, tier)

            # Audit PAC operations
            if tier == ContentTier.PAC and self.config.pac_audit_enabled:
                await self._audit_pac_pin(cid, metadata, selected_path)

            return PinResult(
                cid=cid,
                status=PinStatus.PINNED,
                tier=tier,
                path_used=selected_path,
                coherence=coherence,
            )

        except Exception as e:
            logger.error(f"Pin failed: {e}")
            return PinResult(
                cid=cid,
                status=PinStatus.FAILED,
                tier=tier,
                coherence=coherence,
                error=str(e),
            )

    async def get_via_scion(
        self,
        cid: str,
        tier: ContentTier,
        coherence: float = 0.8,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Retrieve content via SCION path.

        Args:
            cid: IPFS content identifier
            tier: Expected content tier
            coherence: Current coherence score

        Returns:
            Tuple of (content_bytes, error_message)
        """
        # Validate coherence
        if not self._validate_coherence(tier, coherence):
            return None, f"Coherence {coherence} below threshold"

        # Get SCION path
        dest_isd_as = TIER_ISD_AS.get(tier.value.upper(), TIER_ISD_AS["COMN"])
        paths = await self.path_selector.get_paths_for_tier(tier, dest_isd_as)

        if not paths:
            return None, "No SCION paths available"

        try:
            content = await self._fetch_content(cid, paths[0])
            return content, None
        except Exception as e:
            return None, str(e)

    def _validate_coherence(self, tier: ContentTier, coherence: float) -> bool:
        """Validate coherence meets tier requirements."""
        thresholds = {
            ContentTier.CORE: 0.85,
            ContentTier.COMN: 0.80,
            ContentTier.PAC: 0.70,
        }
        return coherence >= thresholds.get(tier, 0.7)

    async def _validate_pac_consent(self, metadata: ContentMetadata) -> bool:
        """Validate PAC consent for content."""
        # In production, would check consent status
        # from PAC Privacy extension or consent database
        return True

    async def _pin_content(self, cid: str, path: str, tier: ContentTier):
        """Pin content to IPFS via SCION path."""
        # In production, would use IPFS HTTP API via SCION
        logger.debug(f"Pinning {cid} via path {path}")
        await asyncio.sleep(0.1)  # Simulate pin operation

    async def _fetch_content(self, cid: str, path: str) -> bytes:
        """Fetch content from IPFS via SCION path."""
        # In production, would use IPFS HTTP API via SCION
        logger.debug(f"Fetching {cid} via path {path}")
        await asyncio.sleep(0.1)
        return b""  # Placeholder

    async def _audit_pac_pin(
        self,
        cid: str,
        metadata: Optional[ContentMetadata],
        path: str,
    ):
        """Send audit event for PAC pin operation."""
        audit_event = {
            "type": "pac_ipfs_pin",
            "cid": cid,
            "path": path,
            "timestamp": time.time(),
            "genesis_bond": GENESIS_BOND_ID,
        }
        if metadata:
            audit_event["owner_did"] = metadata.owner_did

        logger.debug(f"PAC audit: {audit_event}")

    async def _run_server(self):
        """Run HTTP server for bridge API."""
        try:
            from aiohttp import web

            async def pin_handler(request):
                data = await request.json()
                cid = data.get("cid")
                tier = ContentTier(data.get("tier", "comn"))
                coherence = data.get("coherence", 0.8)

                result = await self.pin_via_scion(cid, tier, coherence=coherence)

                return web.json_response({
                    "cid": result.cid,
                    "status": result.status.value,
                    "tier": result.tier.value,
                    "path": result.path_used,
                    "error": result.error,
                })

            async def get_handler(request):
                cid = request.match_info["cid"]
                tier = ContentTier(request.query.get("tier", "comn"))
                coherence = float(request.query.get("coherence", "0.8"))

                content, error = await self.get_via_scion(cid, tier, coherence)

                if error:
                    return web.json_response({"error": error}, status=400)

                return web.Response(body=content or b"")

            async def health_handler(request):
                return web.json_response({
                    "status": "healthy",
                    "genesis_bond": GENESIS_BOND_ID,
                    "local_isd_as": self.config.local_isd_as,
                })

            app = web.Application()
            app.router.add_post("/pin", pin_handler)
            app.router.add_get("/get/{cid}", get_handler)
            app.router.add_get("/health", health_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.config.listen_addr, self.config.listen_port)
            await site.start()

            logger.info(f"IPFS-SCION Bridge API at :{self.config.listen_port}")

            while self._running:
                await asyncio.sleep(1)

        except ImportError:
            logger.error("aiohttp not available")


async def main():
    """Main entry point."""
    config = BridgeConfig()
    bridge = IPFSSCIONBridge(config)

    try:
        await bridge.start()
    except KeyboardInterrupt:
        bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
