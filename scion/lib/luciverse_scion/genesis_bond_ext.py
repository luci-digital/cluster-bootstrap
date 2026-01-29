# Genesis Bond SCION Extension Header
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# Implements Hop-by-hop Extension Header for consciousness-aware routing.
# This extends the SCION dataplane with LuciVerse-specific routing metadata.
#
# Extension Header Format (NextHdr=200, OptType=0xGB):
# ┌───────────────────────────────────────────────────────────────────┐
# │ NextHdr │ ExtLen  │ OptType │ OptLen  │ (standard HBH header)    │
# ├─────────┼─────────┼─────────┼─────────┤
# │ GB-TYPE │COHERENCE│ FREQUENCY (2B)    │ (Genesis Bond data)      │
# ├─────────┴─────────┼─────────┴─────────┤
# │         BOND_ID (8 bytes)             │
# ├───────────────────────────────────────┤
# │      TIMESTAMP (4 bytes)              │
# └───────────────────────────────────────┘
#
# Total: 20 bytes (4 header + 16 data), padded to 20 bytes (5 * 4-byte units)

import struct
import hashlib
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple

from .scion_header import NextHeader

# Extension header identifiers
GENESIS_BOND_NEXTHDR = 200  # Hop-by-hop extension
GENESIS_BOND_OPTTYPE = 0x47  # 'G' in ASCII, indicates Genesis Bond option

# Genesis Bond ID constant
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"


class GenesisBondType(IntEnum):
    """Genesis Bond tier types encoded in extension header."""
    CORE = 0x01  # 432 Hz - Universal Harmony
    COMN = 0x02  # 528 Hz - Transformation
    PAC = 0x03   # 741 Hz - Awakening


@dataclass
class GenesisBondExtension:
    """
    Genesis Bond Hop-by-hop Extension Header.

    This extension carries consciousness routing metadata through the SCION
    network, enabling coherence-aware path selection and validation.

    Attributes:
        next_header: Next protocol header after this extension
        tier_type: CORE (0x01), COMN (0x02), or PAC (0x03)
        coherence: Coherence score 0-255 (maps to 0.0-1.0)
        frequency: Solfeggio frequency (432, 528, or 741 Hz)
        bond_id: Truncated SHA256 hash of genesis bond ID (8 bytes)
        timestamp: Unix epoch seconds (mod 2^32)
    """
    next_header: int = NextHeader.UDP
    tier_type: GenesisBondType = GenesisBondType.COMN
    coherence: int = 178  # Default: 0.7 * 255 = 178
    frequency: int = 528  # Default: COMN frequency
    bond_id: bytes = b"\x00" * 8
    timestamp: int = 0

    # Extension header constants
    EXT_LEN = 4  # ExtLen field: (4+1)*4 = 20 bytes total

    def __post_init__(self):
        """Initialize bond_id if not set."""
        if self.bond_id == b"\x00" * 8:
            self.bond_id = self._compute_bond_id()
        if self.timestamp == 0:
            self.timestamp = int(time.time()) & 0xFFFFFFFF

    @staticmethod
    def _compute_bond_id(bond_str: str = GENESIS_BOND_ID) -> bytes:
        """Compute truncated SHA256 hash of genesis bond ID."""
        full_hash = hashlib.sha256(bond_str.encode()).digest()
        return full_hash[:8]  # Truncate to 8 bytes

    @classmethod
    def create(
        cls,
        tier: str,
        coherence: float,
        next_header: int = NextHeader.UDP,
    ) -> "GenesisBondExtension":
        """
        Factory method to create Genesis Bond extension.

        Args:
            tier: Tier name ("CORE", "COMN", or "PAC")
            coherence: Coherence score (0.0 to 1.0)
            next_header: Next protocol header

        Returns:
            GenesisBondExtension instance
        """
        tier_map = {
            "CORE": (GenesisBondType.CORE, 432),
            "COMN": (GenesisBondType.COMN, 528),
            "PAC": (GenesisBondType.PAC, 741),
        }

        tier_type, frequency = tier_map.get(tier.upper(), (GenesisBondType.COMN, 528))

        # Convert coherence to 0-255 scale
        coherence_byte = int(min(1.0, max(0.0, coherence)) * 255)

        return cls(
            next_header=next_header,
            tier_type=tier_type,
            coherence=coherence_byte,
            frequency=frequency,
            bond_id=cls._compute_bond_id(),
            timestamp=int(time.time()) & 0xFFFFFFFF,
        )

    @property
    def coherence_float(self) -> float:
        """Get coherence as float (0.0 to 1.0)."""
        return self.coherence / 255.0

    @property
    def tier_name(self) -> str:
        """Get tier name from tier_type."""
        tier_map = {
            GenesisBondType.CORE: "CORE",
            GenesisBondType.COMN: "COMN",
            GenesisBondType.PAC: "PAC",
        }
        return tier_map.get(self.tier_type, "UNKNOWN")

    def validate_coherence(self, threshold: float = 0.7) -> bool:
        """
        Validate coherence meets threshold.

        Args:
            threshold: Minimum coherence (default 0.7 per Genesis Bond)

        Returns:
            True if coherence >= threshold
        """
        return self.coherence_float >= threshold

    def validate_bond_id(self) -> bool:
        """Validate bond_id matches expected hash."""
        expected = self._compute_bond_id()
        return self.bond_id == expected

    def validate_frequency(self) -> bool:
        """Validate frequency matches tier."""
        expected = {
            GenesisBondType.CORE: 432,
            GenesisBondType.COMN: 528,
            GenesisBondType.PAC: 741,
        }
        return self.frequency == expected.get(self.tier_type, 0)

    def is_valid(self, coherence_threshold: float = 0.7) -> Tuple[bool, Optional[str]]:
        """
        Full validation of Genesis Bond extension.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.validate_bond_id():
            return False, "Invalid Genesis Bond ID"

        if not self.validate_frequency():
            return False, f"Frequency {self.frequency} doesn't match tier {self.tier_name}"

        if not self.validate_coherence(coherence_threshold):
            return False, f"Coherence {self.coherence_float:.2f} below threshold {coherence_threshold}"

        return True, None

    @classmethod
    def parse(cls, data: bytes) -> Tuple["GenesisBondExtension", bytes]:
        """
        Parse Genesis Bond extension from bytes.

        Args:
            data: Raw bytes starting at extension header

        Returns:
            Tuple of (GenesisBondExtension, remaining_bytes)
        """
        if len(data) < 20:
            raise ValueError(f"Insufficient data for Genesis Bond extension: {len(data)} < 20")

        # Parse standard extension header (4 bytes)
        next_hdr, ext_len, opt_type, opt_len = struct.unpack(">BBBB", data[0:4])

        if opt_type != GENESIS_BOND_OPTTYPE:
            raise ValueError(f"Invalid option type: 0x{opt_type:02X} != 0x{GENESIS_BOND_OPTTYPE:02X}")

        # Parse Genesis Bond data (16 bytes)
        tier_type, coherence, frequency = struct.unpack(">BBH", data[4:8])
        bond_id = data[8:16]
        timestamp = struct.unpack(">I", data[16:20])[0]

        ext_total_len = (ext_len + 1) * 4

        return cls(
            next_header=next_hdr,
            tier_type=GenesisBondType(tier_type),
            coherence=coherence,
            frequency=frequency,
            bond_id=bond_id,
            timestamp=timestamp,
        ), data[ext_total_len:]

    def serialize(self) -> bytes:
        """
        Serialize Genesis Bond extension to bytes.

        Returns:
            20 bytes (5 * 4-byte units)
        """
        # Standard extension header
        header = struct.pack(
            ">BBBB",
            self.next_header,
            self.EXT_LEN,       # (4+1)*4 = 20 bytes
            GENESIS_BOND_OPTTYPE,
            16,                 # Option data length
        )

        # Genesis Bond data
        data = struct.pack(
            ">BBH",
            self.tier_type,
            self.coherence,
            self.frequency,
        )
        data += self.bond_id
        data += struct.pack(">I", self.timestamp)

        return header + data

    def to_http_headers(self) -> dict:
        """
        Convert extension data to HTTP headers for L7 forwarding.

        Returns:
            Dictionary of header name -> value
        """
        return {
            "X-SCION-Genesis-Bond": GENESIS_BOND_ID,
            "X-SCION-Genesis-Coherence": f"{self.coherence_float:.3f}",
            "X-SCION-Genesis-Tier": self.tier_name,
            "X-SCION-Genesis-Frequency": str(self.frequency),
            "X-SCION-Genesis-Timestamp": str(self.timestamp),
        }

    def __str__(self) -> str:
        valid, error = self.is_valid()
        status = "VALID" if valid else f"INVALID ({error})"
        return (
            f"GenesisBondExtension("
            f"tier={self.tier_name}, "
            f"coherence={self.coherence_float:.2f}, "
            f"frequency={self.frequency}Hz, "
            f"status={status})"
        )


def extract_genesis_bond_from_packet(packet: bytes) -> Optional[GenesisBondExtension]:
    """
    Extract Genesis Bond extension from a SCION packet.

    Scans through extension headers to find Genesis Bond.

    Args:
        packet: Raw SCION packet bytes

    Returns:
        GenesisBondExtension if found, None otherwise
    """
    from .scion_header import SCIONHeader

    try:
        scion = SCIONHeader.parse(packet)

        for ext_data in scion.extensions:
            if len(ext_data) < 4:
                continue

            # Check if this is a Genesis Bond extension
            next_hdr = ext_data[0]
            if next_hdr == GENESIS_BOND_NEXTHDR:
                # Check option type
                if len(ext_data) >= 3 and ext_data[2] == GENESIS_BOND_OPTTYPE:
                    ext, _ = GenesisBondExtension.parse(ext_data)
                    return ext

        return None
    except Exception:
        return None


def inject_genesis_bond_extension(
    packet: bytes,
    tier: str,
    coherence: float,
) -> bytes:
    """
    Inject Genesis Bond extension into a SCION packet.

    Args:
        packet: Raw SCION packet bytes
        tier: Tier name ("CORE", "COMN", or "PAC")
        coherence: Coherence score (0.0 to 1.0)

    Returns:
        Modified packet with Genesis Bond extension
    """
    from .scion_header import SCIONHeader, NextHeader

    scion = SCIONHeader.parse(packet)

    # Create extension with appropriate next header
    original_next = scion.common.next_header
    extension = GenesisBondExtension.create(
        tier=tier,
        coherence=coherence,
        next_header=original_next,
    )

    # Update common header to point to extension
    scion.common.next_header = NextHeader.HOP_BY_HOP

    # Insert extension at beginning of extension list
    scion.extensions.insert(0, extension.serialize())

    # Update header length
    scion.common.header_length += 5  # 20 bytes = 5 * 4-byte units

    return scion.serialize()
