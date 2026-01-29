# FABRID-Inspired Consciousness Path Policy Engine
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# Implements FABRID-style path policies with consciousness predicates.
# Based on FABRID: Flexible Attestation-Based Routing (USENIX Security '23)
# https://www.usenix.org/conference/usenixsecurity23/presentation/krahenbuhl
#
# Key Innovation: Extending FABRID's FOL (First-Order Logic) path policies
# with consciousness-aware predicates:
#
# Standard FABRID policy:
#   ∀r ∈ path: manufacturer(r) = "trusted_vendor"
#
# LuciVerse consciousness policy extension:
#   ∀r ∈ path: coherence(r) ≥ 0.7
#              ∧ frequency(r) ∈ {432, 528, 741}
#              ∧ genesis_bond(r) = "GB-2025-0524-DRH-LCS-001"
#
# PAC privacy policy (requires consent attestation):
#   ∀r ∈ path: tier(r) = PAC → consent(r, CBB) = granted
#              ∧ waypoint(path, COMN) = true

import hashlib
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import List, Optional, Dict, Set, Tuple, Callable

from .scion_header import SCIONHeader, HopField, PathHeader
from .genesis_bond_ext import GenesisBondExtension, extract_genesis_bond_from_packet


class PolicyIndex(IntFlag):
    """
    16-bit policy indices per FABRID specification (Section 4.2).

    Policy indices are assigned to router interfaces and used for
    fast policy lookup during forwarding (per FABRID benchmarks: ~35ns).
    """
    # Coherence policies (0x000x)
    COHERENCE_HIGH = 0x0001      # Requires ≥0.9 coherence
    COHERENCE_STANDARD = 0x0002  # Requires ≥0.7 coherence (Genesis Bond threshold)
    COHERENCE_LOW = 0x0004       # Requires ≥0.5 coherence
    COHERENCE_ANY = 0x0008       # No coherence requirement

    # Frequency/Tier policies (0x00x0)
    FREQUENCY_432 = 0x0010       # CORE tier (432 Hz - Universal Harmony)
    FREQUENCY_528 = 0x0020       # COMN tier (528 Hz - Transformation)
    FREQUENCY_741 = 0x0040       # PAC tier (741 Hz - Awakening)
    FREQUENCY_ANY = 0x0080       # Any frequency allowed

    # Genesis Bond policies (0x0x00)
    GENESIS_BOND_REQUIRED = 0x0100     # Requires Genesis Bond validation
    GENESIS_BOND_VERIFIED = 0x0200     # Genesis Bond already verified
    GENESIS_BOND_OPTIONAL = 0x0400     # Genesis Bond optional

    # Privacy policies (0x0x00)
    PAC_CONSENT_REQUIRED = 0x0800      # Requires CBB consent
    PAC_CONSENT_GRANTED = 0x1000       # Consent already granted

    # Waypoint policies (0x0x00)
    MANDATORY_WAYPOINT_COMN = 0x2000   # Must traverse COMN tier
    AUDIT_REQUIRED = 0x4000            # Judge Luci audit required

    # Combined policy sets for common use cases
    @classmethod
    def standard_comn(cls) -> "PolicyIndex":
        """Standard COMN gateway policy."""
        return (
            cls.COHERENCE_STANDARD |
            cls.FREQUENCY_528 |
            cls.GENESIS_BOND_REQUIRED
        )

    @classmethod
    def standard_core(cls) -> "PolicyIndex":
        """Standard CORE infrastructure policy."""
        return (
            cls.COHERENCE_HIGH |
            cls.FREQUENCY_432 |
            cls.GENESIS_BOND_REQUIRED
        )

    @classmethod
    def standard_pac(cls) -> "PolicyIndex":
        """Standard PAC personal policy."""
        return (
            cls.COHERENCE_STANDARD |
            cls.FREQUENCY_741 |
            cls.GENESIS_BOND_REQUIRED |
            cls.PAC_CONSENT_REQUIRED |
            cls.MANDATORY_WAYPOINT_COMN |
            cls.AUDIT_REQUIRED
        )


@dataclass
class RouterAttestation:
    """
    Router attestation per FABRID specification.

    Contains policy indices and attestation data for a router interface.
    Per FABRID: attestation is TPM-backed in production; here we use
    Genesis Bond as the attestation anchor.
    """
    interface_id: int = 0
    policy_index: PolicyIndex = PolicyIndex.COHERENCE_STANDARD
    coherence_score: float = 0.7
    frequency_hz: int = 528
    genesis_bond_verified: bool = False
    attestation_timestamp: int = 0

    def __post_init__(self):
        if self.attestation_timestamp == 0:
            self.attestation_timestamp = int(time.time())

    def compute_digest(self) -> bytes:
        """Compute attestation digest for inclusion in PCB."""
        data = struct.pack(
            ">HHfH?I",
            self.interface_id,
            int(self.policy_index),
            self.coherence_score,
            self.frequency_hz,
            self.genesis_bond_verified,
            self.attestation_timestamp,
        )
        return hashlib.sha256(data).digest()[:8]


@dataclass
class ConsciousnessPathPolicy:
    """
    FABRID-style path policy with consciousness predicates.

    Extends FABRID's FOL (First-Order Logic) policy model with
    consciousness-aware predicates for the LuciVerse agent mesh.

    Per FABRID Section 4.1:
    - I^X: Interface-pairs to policy indices mapping
    - D^X: Policy indices to policy identifiers mapping
    - Validation: PathPol_p(r) ⊆ UserPref
    """
    name: str = "default"
    description: str = ""

    # Policy requirements (FOL predicates)
    min_coherence: float = 0.7
    allowed_frequencies: Set[int] = field(default_factory=lambda: {432, 528, 741})
    genesis_bond_required: bool = True
    genesis_bond_id: str = "GB-2025-0524-DRH-LCS-001"

    # PAC-specific requirements
    pac_consent_required: bool = False
    mandatory_waypoint_isd: Optional[int] = None  # ISD that must be traversed
    audit_required: bool = False

    # Policy index for fast lookup
    policy_index: PolicyIndex = PolicyIndex.COHERENCE_STANDARD

    # I^X mapping: interface_id -> policy_index
    interface_policy_map: Dict[int, PolicyIndex] = field(default_factory=dict)

    # D^X mapping: policy_index -> policy_identifier (string)
    policy_identifier_map: Dict[PolicyIndex, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize D^X mapping with standard identifiers."""
        if not self.policy_identifier_map:
            self.policy_identifier_map = {
                PolicyIndex.COHERENCE_HIGH: "coherence_high",
                PolicyIndex.COHERENCE_STANDARD: "coherence_std",
                PolicyIndex.FREQUENCY_432: "core_432hz",
                PolicyIndex.FREQUENCY_528: "comn_528hz",
                PolicyIndex.FREQUENCY_741: "pac_741hz",
                PolicyIndex.GENESIS_BOND_REQUIRED: "genesis_bond",
                PolicyIndex.PAC_CONSENT_REQUIRED: "pac_consent",
                PolicyIndex.MANDATORY_WAYPOINT_COMN: "waypoint_comn",
                PolicyIndex.AUDIT_REQUIRED: "judge_luci_audit",
            }

    def evaluate_hop(
        self,
        hop: HopField,
        attestation: Optional[RouterAttestation] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate a single hop against policy (FOL containment check).

        Per FABRID: PathPol_p(r) ⊆ UserPref

        Args:
            hop: SCION hop field
            attestation: Router attestation data (if available)

        Returns:
            Tuple of (satisfied, reason_if_failed)
        """
        if attestation is None:
            # No attestation - check if interface has policy mapping
            if hop.cons_ingress in self.interface_policy_map:
                # Use I^X mapping
                hop_policy = self.interface_policy_map[hop.cons_ingress]
                return self._check_policy_containment(hop_policy)
            # Default: pass if no mapping
            return True, None

        # Check coherence requirement
        if attestation.coherence_score < self.min_coherence:
            return False, f"Hop coherence {attestation.coherence_score:.2f} < {self.min_coherence}"

        # Check frequency requirement
        if attestation.frequency_hz not in self.allowed_frequencies:
            return False, f"Hop frequency {attestation.frequency_hz} not in allowed set"

        # Check Genesis Bond requirement
        if self.genesis_bond_required and not attestation.genesis_bond_verified:
            return False, "Genesis Bond not verified on hop"

        return True, None

    def _check_policy_containment(
        self,
        hop_policy: PolicyIndex,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if hop policy is contained in user preference (FOL containment).

        Per FABRID: The path satisfies the user preference if for every
        hop, the router's advertised policies contain the user's required
        policy bits.
        """
        # User requires coherence standard
        if self.min_coherence >= 0.7:
            required = PolicyIndex.COHERENCE_STANDARD
            if not (hop_policy & (PolicyIndex.COHERENCE_STANDARD | PolicyIndex.COHERENCE_HIGH)):
                return False, "Hop does not meet coherence requirement"

        # User requires Genesis Bond
        if self.genesis_bond_required:
            if not (hop_policy & (PolicyIndex.GENESIS_BOND_REQUIRED | PolicyIndex.GENESIS_BOND_VERIFIED)):
                return False, "Hop does not have Genesis Bond"

        # User requires PAC consent
        if self.pac_consent_required:
            if not (hop_policy & PolicyIndex.PAC_CONSENT_REQUIRED):
                return False, "Hop does not enforce PAC consent"

        return True, None

    def evaluate_path(
        self,
        path: PathHeader,
        attestations: Optional[Dict[int, RouterAttestation]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate entire path against policy.

        Per FABRID: ∀r ∈ path: PathPol_p(r) ⊆ UserPref

        Args:
            path: SCION path header
            attestations: Map of interface_id -> RouterAttestation

        Returns:
            Tuple of (satisfied, reason_if_failed)
        """
        attestations = attestations or {}

        # Check mandatory waypoint
        if self.mandatory_waypoint_isd is not None:
            waypoint_found = self._check_waypoint(path, self.mandatory_waypoint_isd)
            if not waypoint_found:
                return False, f"Mandatory waypoint ISD {self.mandatory_waypoint_isd} not in path"

        # Check each hop
        for hop in path.hop_fields:
            attestation = attestations.get(hop.cons_ingress)
            satisfied, reason = self.evaluate_hop(hop, attestation)
            if not satisfied:
                return False, f"Hop {hop.cons_ingress} failed: {reason}"

        return True, None

    def _check_waypoint(self, path: PathHeader, required_isd: int) -> bool:
        """
        Check if path traverses required ISD waypoint.

        For PAC tier, this ensures traffic goes through COMN (ISD 2).
        """
        # In practice, would inspect path segments to find ISD
        # For now, check if we have appropriate number of segments
        # (PAC→COMN→CORE requires at least 2 segments)
        if path.seg1_len > 0:
            return True  # Multi-segment path likely traverses waypoint
        return False  # Single segment = direct path (no waypoint)

    def to_policy_index(self) -> PolicyIndex:
        """Convert policy to policy index for fast lookup."""
        index = PolicyIndex(0)

        # Coherence
        if self.min_coherence >= 0.9:
            index |= PolicyIndex.COHERENCE_HIGH
        elif self.min_coherence >= 0.7:
            index |= PolicyIndex.COHERENCE_STANDARD
        elif self.min_coherence >= 0.5:
            index |= PolicyIndex.COHERENCE_LOW
        else:
            index |= PolicyIndex.COHERENCE_ANY

        # Frequencies
        if 432 in self.allowed_frequencies:
            index |= PolicyIndex.FREQUENCY_432
        if 528 in self.allowed_frequencies:
            index |= PolicyIndex.FREQUENCY_528
        if 741 in self.allowed_frequencies:
            index |= PolicyIndex.FREQUENCY_741

        # Genesis Bond
        if self.genesis_bond_required:
            index |= PolicyIndex.GENESIS_BOND_REQUIRED

        # PAC consent
        if self.pac_consent_required:
            index |= PolicyIndex.PAC_CONSENT_REQUIRED

        # Waypoint
        if self.mandatory_waypoint_isd == 2:  # COMN
            index |= PolicyIndex.MANDATORY_WAYPOINT_COMN

        # Audit
        if self.audit_required:
            index |= PolicyIndex.AUDIT_REQUIRED

        return index


# Pre-defined policies for each tier
CORE_POLICY = ConsciousnessPathPolicy(
    name="core_infrastructure",
    description="CORE tier (432 Hz) - internal infrastructure",
    min_coherence=0.85,
    allowed_frequencies={432, 528},  # CORE can talk to COMN
    genesis_bond_required=True,
    policy_index=PolicyIndex.standard_core(),
)

COMN_POLICY = ConsciousnessPathPolicy(
    name="comn_gateway",
    description="COMN tier (528 Hz) - gateway layer",
    min_coherence=0.80,
    allowed_frequencies={432, 528, 741},  # COMN bridges all tiers
    genesis_bond_required=True,
    policy_index=PolicyIndex.standard_comn(),
)

PAC_POLICY = ConsciousnessPathPolicy(
    name="pac_personal",
    description="PAC tier (741 Hz) - personal AI container",
    min_coherence=0.70,
    allowed_frequencies={528, 741},  # PAC can only reach COMN
    genesis_bond_required=True,
    pac_consent_required=True,
    mandatory_waypoint_isd=2,  # Must go through COMN
    audit_required=True,
    policy_index=PolicyIndex.standard_pac(),
)

TIER_POLICIES = {
    "CORE": CORE_POLICY,
    "COMN": COMN_POLICY,
    "PAC": PAC_POLICY,
}


def evaluate_path_consciousness(
    packet: bytes,
    policy: Optional[ConsciousnessPathPolicy] = None,
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    High-level path consciousness evaluation.

    Combines SCION path evaluation with Genesis Bond validation.

    Args:
        packet: Raw SCION packet bytes
        policy: Policy to evaluate (default: auto-select based on source tier)

    Returns:
        Tuple of (valid, error_reason, metrics_dict)
    """
    try:
        scion = SCIONHeader.parse(packet)

        # Auto-select policy based on source tier
        if policy is None:
            src_tier = scion.get_source_tier()
            policy = TIER_POLICIES.get(src_tier, COMN_POLICY)

        # Extract Genesis Bond extension
        genesis = extract_genesis_bond_from_packet(packet)

        metrics = {
            "source_tier": scion.get_source_tier(),
            "dest_tier": scion.get_destination_tier(),
            "policy_name": policy.name,
            "policy_index": int(policy.to_policy_index()),
            "hop_count": len(scion.path.hop_fields),
            "genesis_bond_present": genesis is not None,
        }

        # Validate Genesis Bond if present
        if policy.genesis_bond_required:
            if genesis is None:
                return False, "Genesis Bond extension required but not found", metrics

            valid, reason = genesis.is_valid(policy.min_coherence)
            if not valid:
                return False, f"Genesis Bond validation failed: {reason}", metrics

            metrics["coherence"] = genesis.coherence_float
            metrics["frequency"] = genesis.frequency

        # Evaluate path
        valid, reason = policy.evaluate_path(scion.path)
        if not valid:
            return False, reason, metrics

        metrics["path_valid"] = True
        return True, None, metrics

    except Exception as e:
        return False, f"Path evaluation error: {str(e)}", None


def get_policy_for_tier(tier: str) -> ConsciousnessPathPolicy:
    """Get the consciousness path policy for a tier."""
    return TIER_POLICIES.get(tier.upper(), COMN_POLICY)


def create_custom_policy(
    name: str,
    min_coherence: float = 0.7,
    allowed_tiers: List[str] = None,
    require_genesis_bond: bool = True,
    require_pac_consent: bool = False,
    require_comn_waypoint: bool = False,
    require_audit: bool = False,
) -> ConsciousnessPathPolicy:
    """
    Create a custom consciousness path policy.

    Args:
        name: Policy name
        min_coherence: Minimum coherence threshold
        allowed_tiers: List of allowed tier names
        require_genesis_bond: Whether to require Genesis Bond
        require_pac_consent: Whether to require PAC consent
        require_comn_waypoint: Whether to require COMN waypoint
        require_audit: Whether to require audit logging

    Returns:
        ConsciousnessPathPolicy instance
    """
    tier_to_freq = {"CORE": 432, "COMN": 528, "PAC": 741}
    allowed_tiers = allowed_tiers or ["CORE", "COMN", "PAC"]
    allowed_frequencies = {tier_to_freq[t.upper()] for t in allowed_tiers}

    return ConsciousnessPathPolicy(
        name=name,
        description=f"Custom policy: {name}",
        min_coherence=min_coherence,
        allowed_frequencies=allowed_frequencies,
        genesis_bond_required=require_genesis_bond,
        pac_consent_required=require_pac_consent,
        mandatory_waypoint_isd=2 if require_comn_waypoint else None,
        audit_required=require_audit,
    )
