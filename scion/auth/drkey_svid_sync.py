#!/usr/bin/env python3
"""
DRKey-SVID Synchronization Module
Genesis Bond: GB-2025-0524-DRH-LCS-001

This module synchronizes SCION DRKey Level 3 keys with SPIFFE SVID
(SPIFFE Verifiable Identity Documents) rotation. Both systems use
a 15-minute key lifetime, but operate independently by default.

This synchronization ensures:
1. DRKey L3 derivation incorporates SPIFFE identity
2. Key rotation happens at aligned intervals
3. Cross-system authentication is seamless

Per SCION DRKey specification:
- Level 1: 24h validity (AS-to-AS)
- Level 2: 1h validity (host-to-host)
- Level 3: 15m validity (application-level)

Per SPIFFE SVID specification:
- Default TTL: 15 minutes
- Trust domain: luciverse.ownid
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("drkey-svid-sync")

# Constants
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
SPIFFE_TRUST_DOMAIN = "luciverse.ownid"
KEY_LIFETIME_SECONDS = 900  # 15 minutes
ROTATION_GRACE_SECONDS = 60  # Start rotation 1 minute before expiry


class KeyTier(Enum):
    """Key derivation tiers matching LuciVerse architecture."""
    CORE = "core"  # 432 Hz
    COMN = "comn"  # 528 Hz
    PAC = "pac"    # 741 Hz


@dataclass
class DRKeyL3:
    """
    SCION DRKey Level 3 key.

    Level 3 keys are derived from Level 2 keys and are specific
    to a particular protocol/application endpoint.
    """
    key: bytes
    src_isd_as: str
    dst_isd_as: str
    protocol: str
    validity_start: float
    validity_end: float
    derived_from_svid: bool = False
    svid_hash: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if key is currently valid."""
        now = time.time()
        return self.validity_start <= now <= self.validity_end

    @property
    def remaining_seconds(self) -> float:
        """Seconds until key expires."""
        return max(0, self.validity_end - time.time())

    @property
    def needs_rotation(self) -> bool:
        """Check if key should be rotated."""
        return self.remaining_seconds < ROTATION_GRACE_SECONDS


@dataclass
class SVID:
    """
    SPIFFE Verifiable Identity Document.

    Represents a SPIFFE identity with its associated X.509 certificate.
    """
    spiffe_id: str
    trust_domain: str
    certificate_pem: str
    private_key_pem: str
    not_before: float
    not_after: float
    serial_number: str
    tier: KeyTier = KeyTier.COMN

    @property
    def is_valid(self) -> bool:
        """Check if SVID is currently valid."""
        now = time.time()
        return self.not_before <= now <= self.not_after

    @property
    def remaining_seconds(self) -> float:
        """Seconds until SVID expires."""
        return max(0, self.not_after - time.time())

    @property
    def needs_rotation(self) -> bool:
        """Check if SVID should be rotated."""
        return self.remaining_seconds < ROTATION_GRACE_SECONDS

    def compute_hash(self) -> str:
        """Compute hash of SVID for binding to DRKey."""
        data = f"{self.spiffe_id}:{self.serial_number}:{self.not_before}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class SyncConfig:
    """Configuration for DRKey-SVID synchronization."""
    # SCION DRKey settings
    drkey_socket: str = "/var/run/scion/drkey.sock"
    drkey_api: str = "http://localhost:30255/drkey"

    # SPIFFE Workload API
    spiffe_socket: str = "/var/run/spiffe/agent.sock"
    spiffe_api: str = "http://localhost:8443/v2"

    # 1Password Connect (for SVID storage)
    op_connect_url: str = "http://192.168.1.152:8082"
    op_vault: str = "Infrastructure"

    # Synchronization settings
    key_lifetime: int = KEY_LIFETIME_SECONDS
    rotation_grace: int = ROTATION_GRACE_SECONDS
    sync_interval: float = 30.0  # Check every 30 seconds

    # Key derivation
    kdf_algorithm: str = "PBKDF2-SHA256"
    kdf_iterations: int = 100000
    genesis_bond_in_salt: bool = True

    # Tier-specific settings
    tier_frequencies: Dict[KeyTier, int] = field(default_factory=lambda: {
        KeyTier.CORE: 432,
        KeyTier.COMN: 528,
        KeyTier.PAC: 741,
    })


class DRKeySVIDSync:
    """
    Synchronize SCION DRKey L3 with SPIFFE SVID rotation.

    This class manages the lifecycle of both key systems,
    ensuring they rotate together and DRKey derivation
    incorporates SPIFFE identity for unified authentication.
    """

    def __init__(self, config: SyncConfig):
        self.config = config
        self._running = False
        self._current_svid: Optional[SVID] = None
        self._drkey_cache: Dict[str, DRKeyL3] = {}
        self._rotation_lock = asyncio.Lock()

    async def start(self):
        """Start the synchronization service."""
        self._running = True
        logger.info("DRKey-SVID synchronization starting")

        # Initial SVID fetch
        await self._fetch_svid()

        # Start sync loop
        await self._sync_loop()

    def stop(self):
        """Stop the synchronization service."""
        self._running = False
        logger.info("DRKey-SVID synchronization stopping")

    async def _sync_loop(self):
        """Main synchronization loop."""
        while self._running:
            try:
                await self._check_and_rotate()
            except Exception as e:
                logger.error(f"Sync error: {e}")

            await asyncio.sleep(self.config.sync_interval)

    async def _check_and_rotate(self):
        """Check if rotation is needed and perform it."""
        async with self._rotation_lock:
            # Check SVID
            if self._current_svid is None or self._current_svid.needs_rotation:
                logger.info("SVID rotation needed")
                await self._rotate_svid()

            # Check DRKeys
            for key_id, drkey in list(self._drkey_cache.items()):
                if drkey.needs_rotation:
                    logger.info(f"DRKey rotation needed: {key_id}")
                    await self._rotate_drkey(key_id)

    async def _fetch_svid(self):
        """Fetch current SVID from SPIFFE Workload API."""
        try:
            # In production, would use SPIFFE Workload API
            # For now, simulate SVID
            now = time.time()
            self._current_svid = SVID(
                spiffe_id=f"spiffe://{SPIFFE_TRUST_DOMAIN}/comn/agents/sig",
                trust_domain=SPIFFE_TRUST_DOMAIN,
                certificate_pem="",  # Would be actual cert
                private_key_pem="",  # Would be actual key
                not_before=now,
                not_after=now + self.config.key_lifetime,
                serial_number=hashlib.sha256(str(now).encode()).hexdigest()[:16],
                tier=KeyTier.COMN,
            )
            logger.info(f"SVID fetched: {self._current_svid.spiffe_id}")
        except Exception as e:
            logger.error(f"Failed to fetch SVID: {e}")

    async def _rotate_svid(self):
        """Rotate SVID and update all dependent DRKeys."""
        # Fetch new SVID
        await self._fetch_svid()

        if self._current_svid is None:
            return

        # Rotate all DRKeys with new SVID binding
        for key_id in list(self._drkey_cache.keys()):
            await self._rotate_drkey(key_id)

        logger.info("SVID rotation complete, DRKeys updated")

    async def _rotate_drkey(self, key_id: str):
        """Rotate a specific DRKey."""
        if key_id not in self._drkey_cache:
            return

        old_key = self._drkey_cache[key_id]

        # Derive new key
        new_key = await self._derive_drkey_l3(
            src_isd_as=old_key.src_isd_as,
            dst_isd_as=old_key.dst_isd_as,
            protocol=old_key.protocol,
        )

        self._drkey_cache[key_id] = new_key
        logger.debug(f"DRKey rotated: {key_id}")

    async def _derive_drkey_l3(
        self,
        src_isd_as: str,
        dst_isd_as: str,
        protocol: str,
    ) -> DRKeyL3:
        """
        Derive DRKey Level 3 with SVID binding.

        The key derivation includes SVID hash in the salt,
        cryptographically binding SCION and SPIFFE identities.
        """
        now = time.time()

        # Build salt with SVID binding
        salt_parts = [
            f"LuciVerse-DRKey-L3",
            src_isd_as,
            dst_isd_as,
            protocol,
            str(int(now / self.config.key_lifetime)),  # Time bucket
        ]

        if self.config.genesis_bond_in_salt:
            salt_parts.append(GENESIS_BOND_ID)

        if self._current_svid:
            salt_parts.append(self._current_svid.compute_hash())
            svid_hash = self._current_svid.compute_hash()
        else:
            svid_hash = ""

        # Determine tier and add frequency
        tier = self._get_tier_from_isd_as(src_isd_as)
        frequency = self.config.tier_frequencies.get(tier, 528)
        salt_parts.append(f"{frequency}Hz")

        salt = ":".join(salt_parts).encode()

        # Master key (in production, would come from DRKey L2)
        master_key = self._get_master_key(src_isd_as, dst_isd_as)

        # Derive key using PBKDF2
        key = self._pbkdf2_derive(
            password=master_key,
            salt=salt,
            iterations=self.config.kdf_iterations,
            key_length=32,
        )

        return DRKeyL3(
            key=key,
            src_isd_as=src_isd_as,
            dst_isd_as=dst_isd_as,
            protocol=protocol,
            validity_start=now,
            validity_end=now + self.config.key_lifetime,
            derived_from_svid=bool(self._current_svid),
            svid_hash=svid_hash,
        )

    def _get_master_key(self, src_isd_as: str, dst_isd_as: str) -> bytes:
        """
        Get master key for DRKey derivation.

        In production, this would come from SCION DRKey L2.
        Here we derive from Genesis Bond for consistency.
        """
        data = f"{GENESIS_BOND_ID}:{src_isd_as}:{dst_isd_as}"
        return hashlib.sha256(data.encode()).digest()

    def _pbkdf2_derive(
        self,
        password: bytes,
        salt: bytes,
        iterations: int,
        key_length: int,
    ) -> bytes:
        """Derive key using PBKDF2-SHA256."""
        import hashlib
        return hashlib.pbkdf2_hmac(
            "sha256",
            password,
            salt,
            iterations,
            dklen=key_length,
        )

    def _get_tier_from_isd_as(self, isd_as: str) -> KeyTier:
        """Get tier from ISD-AS identifier."""
        isd = int(isd_as.split("-")[0])
        tier_map = {1: KeyTier.CORE, 2: KeyTier.COMN, 3: KeyTier.PAC}
        return tier_map.get(isd, KeyTier.COMN)

    # Public API

    async def get_drkey(
        self,
        src_isd_as: str,
        dst_isd_as: str,
        protocol: str = "luciverse",
    ) -> DRKeyL3:
        """
        Get a DRKey L3 for the specified parameters.

        Creates and caches the key if it doesn't exist.
        """
        key_id = f"{src_isd_as}:{dst_isd_as}:{protocol}"

        if key_id not in self._drkey_cache or self._drkey_cache[key_id].needs_rotation:
            self._drkey_cache[key_id] = await self._derive_drkey_l3(
                src_isd_as=src_isd_as,
                dst_isd_as=dst_isd_as,
                protocol=protocol,
            )

        return self._drkey_cache[key_id]

    def get_current_svid(self) -> Optional[SVID]:
        """Get the current SVID."""
        return self._current_svid

    def get_sync_status(self) -> dict:
        """Get current synchronization status."""
        return {
            "running": self._running,
            "svid": {
                "present": self._current_svid is not None,
                "spiffe_id": self._current_svid.spiffe_id if self._current_svid else None,
                "remaining_seconds": self._current_svid.remaining_seconds if self._current_svid else 0,
                "needs_rotation": self._current_svid.needs_rotation if self._current_svid else True,
            },
            "drkey_cache_size": len(self._drkey_cache),
            "config": {
                "key_lifetime": self.config.key_lifetime,
                "rotation_grace": self.config.rotation_grace,
                "sync_interval": self.config.sync_interval,
            },
        }


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="DRKey-SVID Synchronization")
    parser.add_argument(
        "--spiffe-socket",
        default="/var/run/spiffe/agent.sock",
        help="SPIFFE Workload API socket",
    )
    parser.add_argument(
        "--drkey-socket",
        default="/var/run/scion/drkey.sock",
        help="SCION DRKey socket",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = SyncConfig(
        spiffe_socket=args.spiffe_socket,
        drkey_socket=args.drkey_socket,
    )

    sync = DRKeySVIDSync(config)

    try:
        await sync.start()
    except KeyboardInterrupt:
        sync.stop()


if __name__ == "__main__":
    asyncio.run(main())
