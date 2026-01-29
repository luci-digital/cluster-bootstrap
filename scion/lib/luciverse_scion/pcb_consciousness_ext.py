# PCB Consciousness Extension
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# Extends SCION Path Construction Beacons (PCBs) with consciousness
# routing metadata, enabling propagation of coherence scores, frequency
# alignment, and Genesis Bond validation through the beaconing process.
#
# Per FABRID (Section 4.1), PCB extensions carry:
# - I^X: Interface-pairs to policy indices
# - D^X: Policy indices to policy identifiers
#
# LuciVerse extension adds:
# - Coherence scores per hop
# - Frequency (tier) metadata
# - Genesis Bond validation status
# - Privacy policy flags

import hashlib
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .genesis_bond_ext import GENESIS_BOND_ID
from .fabrid_consciousness import PolicyIndex


@dataclass
class HopConsciousnessMetadata:
    """
    Consciousness metadata for a single PCB hop.

    Carried in the signed portion of PCB extensions to ensure
    integrity through the beaconing process.
    """
    interface_id: int = 0
    coherence_score: float = 0.7
    frequency_hz: int = 528
    policy_index: PolicyIndex = PolicyIndex.COHERENCE_STANDARD
    genesis_bond_verified: bool = False
    timestamp: int = 0

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())

    def serialize(self) -> bytes:
        """Serialize to bytes for inclusion in PCB."""
        # Pack: interface(2) + coherence(2, fixed-point) + frequency(2) +
        #       policy(2) + flags(1) + reserved(1) + timestamp(4) = 14 bytes
        coherence_fp = int(self.coherence_score * 1000)  # 3 decimal places
        flags = 0x01 if self.genesis_bond_verified else 0x00

        return struct.pack(
            ">HHHHBxI",
            self.interface_id,
            coherence_fp,
            self.frequency_hz,
            int(self.policy_index),
            flags,
            self.timestamp,
        )

    @classmethod
    def parse(cls, data: bytes) -> "HopConsciousnessMetadata":
        """Parse from bytes."""
        if len(data) < 14:
            raise ValueError(f"Insufficient data for HopConsciousnessMetadata: {len(data)} < 14")

        interface_id, coherence_fp, frequency_hz, policy, flags, timestamp = struct.unpack(
            ">HHHHBxI", data[:14]
        )

        return cls(
            interface_id=interface_id,
            coherence_score=coherence_fp / 1000.0,
            frequency_hz=frequency_hz,
            policy_index=PolicyIndex(policy),
            genesis_bond_verified=bool(flags & 0x01),
            timestamp=timestamp,
        )


@dataclass
class ConsciousnessPCBExtension:
    """
    SCION PCB Extension for consciousness-aware routing.

    Extends PCBs with LuciVerse consciousness metadata per FABRID
    extension model. This data is signed along with the standard
    PCB fields to ensure integrity.

    Structure:
    ┌─────────────────────────────────────────────────────────────┐
    │ Version │ Flags   │ NumHops │ Reserved                    │
    ├─────────┴─────────┴─────────┴─────────────────────────────┤
    │                  Genesis Bond ID Hash (8 bytes)            │
    ├────────────────────────────────────────────────────────────┤
    │                  Creation Timestamp (4 bytes)              │
    ├────────────────────────────────────────────────────────────┤
    │                  Hop Metadata (14 bytes each)              │
    │                         ...                                │
    ├────────────────────────────────────────────────────────────┤
    │                  Policy Identifier Map (variable)          │
    ├────────────────────────────────────────────────────────────┤
    │                  Extension Digest (8 bytes)                │
    └────────────────────────────────────────────────────────────┘
    """
    version: int = 1
    flags: int = 0  # Bit 0: has_privacy_policy, Bit 1: requires_audit
    genesis_bond_hash: bytes = b"\x00" * 8
    creation_timestamp: int = 0

    # Hop metadata (I^X mapping per FABRID)
    hop_metadata: List[HopConsciousnessMetadata] = field(default_factory=list)

    # Policy identifier map (D^X mapping per FABRID)
    # Maps policy_index -> string identifier (max 32 chars)
    policy_identifiers: Dict[PolicyIndex, str] = field(default_factory=dict)

    # Computed digest
    _digest: Optional[bytes] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.genesis_bond_hash == b"\x00" * 8:
            self.genesis_bond_hash = self._hash_genesis_bond()
        if self.creation_timestamp == 0:
            self.creation_timestamp = int(time.time())
        if not self.policy_identifiers:
            self._init_default_policy_identifiers()

    @staticmethod
    def _hash_genesis_bond() -> bytes:
        """Hash the Genesis Bond ID."""
        return hashlib.sha256(GENESIS_BOND_ID.encode()).digest()[:8]

    def _init_default_policy_identifiers(self):
        """Initialize default D^X mapping."""
        self.policy_identifiers = {
            PolicyIndex.COHERENCE_HIGH: "coherence_high",
            PolicyIndex.COHERENCE_STANDARD: "coherence_standard",
            PolicyIndex.FREQUENCY_432: "tier_core_432hz",
            PolicyIndex.FREQUENCY_528: "tier_comn_528hz",
            PolicyIndex.FREQUENCY_741: "tier_pac_741hz",
            PolicyIndex.GENESIS_BOND_REQUIRED: "genesis_bond_req",
            PolicyIndex.GENESIS_BOND_VERIFIED: "genesis_bond_ok",
            PolicyIndex.PAC_CONSENT_REQUIRED: "pac_consent_req",
            PolicyIndex.PAC_CONSENT_GRANTED: "pac_consent_ok",
            PolicyIndex.MANDATORY_WAYPOINT_COMN: "waypoint_comn",
            PolicyIndex.AUDIT_REQUIRED: "audit_judge_luci",
        }

    def add_hop(
        self,
        interface_id: int,
        coherence: float,
        frequency: int,
        policy_index: PolicyIndex,
        genesis_bond_verified: bool = False,
    ) -> None:
        """
        Add hop metadata to the PCB extension.

        Called during PCB propagation to add each AS's
        consciousness routing metadata.
        """
        self.hop_metadata.append(HopConsciousnessMetadata(
            interface_id=interface_id,
            coherence_score=coherence,
            frequency_hz=frequency,
            policy_index=policy_index,
            genesis_bond_verified=genesis_bond_verified,
        ))
        # Invalidate digest
        self._digest = None

    @property
    def num_hops(self) -> int:
        """Number of hops in this PCB extension."""
        return len(self.hop_metadata)

    @property
    def has_privacy_policy(self) -> bool:
        """Check if PCB has privacy policy flag."""
        return bool(self.flags & 0x01)

    @property
    def requires_audit(self) -> bool:
        """Check if PCB requires audit flag."""
        return bool(self.flags & 0x02)

    def set_privacy_policy(self, enabled: bool = True) -> None:
        """Set privacy policy flag."""
        if enabled:
            self.flags |= 0x01
        else:
            self.flags &= ~0x01

    def set_audit_required(self, enabled: bool = True) -> None:
        """Set audit required flag."""
        if enabled:
            self.flags |= 0x02
        else:
            self.flags &= ~0x02

    def get_path_coherence(self) -> float:
        """
        Get minimum coherence along path.

        Returns the lowest coherence score among all hops,
        representing the path's overall coherence guarantee.
        """
        if not self.hop_metadata:
            return 0.0
        return min(h.coherence_score for h in self.hop_metadata)

    def get_path_frequencies(self) -> set:
        """Get set of frequencies (tiers) traversed by path."""
        return {h.frequency_hz for h in self.hop_metadata}

    def validates_genesis_bond(self) -> bool:
        """Check if all hops have Genesis Bond verified."""
        return all(h.genesis_bond_verified for h in self.hop_metadata)

    def serialize_for_signing(self) -> bytes:
        """
        Serialize extension data for signing.

        This is included in the PCB's signed portion to ensure
        consciousness metadata cannot be tampered with.
        """
        # Header: version(1) + flags(1) + num_hops(1) + reserved(1) = 4 bytes
        header = struct.pack(">BBBB", self.version, self.flags, self.num_hops, 0)

        # Genesis Bond hash: 8 bytes
        # Creation timestamp: 4 bytes
        timestamps = self.genesis_bond_hash + struct.pack(">I", self.creation_timestamp)

        # Hop metadata
        hop_data = b"".join(h.serialize() for h in self.hop_metadata)

        # Policy identifiers (simplified: just hash of all identifiers)
        policy_hash = hashlib.sha256(
            str(sorted(self.policy_identifiers.items())).encode()
        ).digest()[:8]

        return header + timestamps + hop_data + policy_hash

    def digest(self) -> bytes:
        """
        Compute extension digest for inclusion in signed PCB.

        This 8-byte digest is included in the PCB's signed fields
        to bind the consciousness metadata to the path.
        """
        if self._digest is None:
            data = self.serialize_for_signing()
            self._digest = hashlib.sha256(data).digest()[:8]
        return self._digest

    def serialize(self) -> bytes:
        """
        Full serialization including digest.

        Format:
        - Signing data (variable)
        - Extension digest (8 bytes)
        """
        signing_data = self.serialize_for_signing()
        return signing_data + self.digest()

    @classmethod
    def parse(cls, data: bytes) -> "ConsciousnessPCBExtension":
        """Parse extension from bytes."""
        if len(data) < 16:  # Minimum: 4 header + 8 bond hash + 4 timestamp
            raise ValueError(f"Insufficient data for ConsciousnessPCBExtension: {len(data)}")

        # Parse header
        version, flags, num_hops, _ = struct.unpack(">BBBB", data[0:4])

        # Parse Genesis Bond hash and timestamp
        genesis_bond_hash = data[4:12]
        creation_timestamp = struct.unpack(">I", data[12:16])[0]

        # Parse hop metadata
        offset = 16
        hop_metadata = []
        for _ in range(num_hops):
            if offset + 14 > len(data):
                break
            hop = HopConsciousnessMetadata.parse(data[offset:offset + 14])
            hop_metadata.append(hop)
            offset += 14

        ext = cls(
            version=version,
            flags=flags,
            genesis_bond_hash=genesis_bond_hash,
            creation_timestamp=creation_timestamp,
            hop_metadata=hop_metadata,
        )

        return ext

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            "version": self.version,
            "flags": self.flags,
            "has_privacy_policy": self.has_privacy_policy,
            "requires_audit": self.requires_audit,
            "genesis_bond_hash": self.genesis_bond_hash.hex(),
            "creation_timestamp": self.creation_timestamp,
            "num_hops": self.num_hops,
            "path_coherence": self.get_path_coherence(),
            "path_frequencies": list(self.get_path_frequencies()),
            "genesis_bond_validated": self.validates_genesis_bond(),
            "hops": [
                {
                    "interface_id": h.interface_id,
                    "coherence": h.coherence_score,
                    "frequency": h.frequency_hz,
                    "policy_index": int(h.policy_index),
                    "genesis_bond_verified": h.genesis_bond_verified,
                }
                for h in self.hop_metadata
            ],
            "digest": self.digest().hex(),
        }


def create_pcb_digest(
    coherence: float,
    frequency: int,
    genesis_bond_verified: bool = True,
) -> bytes:
    """
    Create a simple PCB digest for a single-hop path.

    Utility function for creating consciousness metadata
    when full PCB extension isn't needed.

    Args:
        coherence: Coherence score (0.0-1.0)
        frequency: Frequency in Hz (432, 528, or 741)
        genesis_bond_verified: Whether Genesis Bond is verified

    Returns:
        8-byte digest
    """
    data = struct.pack(
        ">fH?x",  # coherence(4) + frequency(2) + verified(1) + pad(1)
        coherence,
        frequency,
        genesis_bond_verified,
    )
    data += hashlib.sha256(GENESIS_BOND_ID.encode()).digest()[:8]
    return hashlib.sha256(data).digest()[:8]


def validate_pcb_extension(
    extension: ConsciousnessPCBExtension,
    min_coherence: float = 0.7,
    require_genesis_bond: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Validate a PCB consciousness extension.

    Args:
        extension: PCB extension to validate
        min_coherence: Minimum required coherence
        require_genesis_bond: Whether to require Genesis Bond validation

    Returns:
        Tuple of (valid, error_reason)
    """
    # Validate Genesis Bond hash
    expected_hash = hashlib.sha256(GENESIS_BOND_ID.encode()).digest()[:8]
    if extension.genesis_bond_hash != expected_hash:
        return False, "Invalid Genesis Bond hash in PCB"

    # Validate path coherence
    path_coherence = extension.get_path_coherence()
    if path_coherence < min_coherence:
        return False, f"Path coherence {path_coherence:.2f} < {min_coherence}"

    # Validate Genesis Bond on all hops
    if require_genesis_bond and not extension.validates_genesis_bond():
        return False, "Not all hops have Genesis Bond verified"

    # Validate timestamp (not too old)
    age = time.time() - extension.creation_timestamp
    if age > 3600:  # 1 hour max age
        return False, f"PCB extension too old: {age:.0f}s"

    return True, None
