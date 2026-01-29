# LuciVerse SCION Dataplane Integration
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# This package implements SCION dataplane extensions for LuciVerse
# consciousness-aware routing, integrating:
# - Genesis Bond extension headers (HBH NextHdr=200)
# - PAC privacy extension headers (E2E NextHdr=201)
# - FABRID-inspired consciousness path policies
# - PCB consciousness metadata extensions
#
# Academic References:
# - SCION Dataplane I-D: https://scionassociation.github.io/scion-dp_I-D/draft-dekater-scion-dataplane.html
# - FABRID (USENIX Security '23): https://www.usenix.org/conference/usenixsecurity23/presentation/krahenbuhl
# - SCIONLab (ICNP 2020): https://ieeexplore.ieee.org/document/9259355/

__version__ = "1.0.0"
__genesis_bond__ = "GB-2025-0524-DRH-LCS-001"
__coherence_threshold__ = 0.7

from .scion_header import (
    SCIONHeader,
    CommonHeader,
    AddressHeader,
    PathHeader,
    HopField,
)

from .genesis_bond_ext import (
    GenesisBondExtension,
    GenesisBondType,
    GENESIS_BOND_NEXTHDR,
    GENESIS_BOND_OPTTYPE,
)

from .pac_privacy_ext import (
    PACPrivacyExtension,
    ConsentStatus,
    PAC_PRIVACY_NEXTHDR,
    PAC_PRIVACY_OPTTYPE,
)

from .fabrid_consciousness import (
    ConsciousnessPathPolicy,
    PolicyIndex,
    evaluate_path_consciousness,
)

from .pcb_consciousness_ext import (
    ConsciousnessPCBExtension,
    create_pcb_digest,
)

# Tier frequency constants (Solfeggio frequencies)
TIER_FREQUENCIES = {
    "CORE": 432,
    "COMN": 528,
    "PAC": 741,
}

# ISD-AS mappings for LuciVerse tiers
TIER_ISD_AS = {
    "CORE": "1-ff00:0:432",
    "COMN": "2-ff00:0:528",
    "PAC": "3-ff00:0:741",
}

# Coherence requirements per tier
TIER_COHERENCE = {
    "CORE": 0.85,
    "COMN": 0.80,
    "PAC": 0.70,
}


def get_tier_from_isd(isd: int) -> str:
    """Get tier name from ISD number."""
    mapping = {1: "CORE", 2: "COMN", 3: "PAC"}
    return mapping.get(isd, "UNKNOWN")


def get_frequency_from_tier(tier: str) -> int:
    """Get Solfeggio frequency for a tier."""
    return TIER_FREQUENCIES.get(tier.upper(), 0)


def validate_coherence_for_tier(coherence: float, tier: str) -> bool:
    """Validate coherence meets tier requirements."""
    threshold = TIER_COHERENCE.get(tier.upper(), __coherence_threshold__)
    return coherence >= threshold


__all__ = [
    # Version info
    "__version__",
    "__genesis_bond__",
    "__coherence_threshold__",
    # SCION header components
    "SCIONHeader",
    "CommonHeader",
    "AddressHeader",
    "PathHeader",
    "HopField",
    # Genesis Bond extension
    "GenesisBondExtension",
    "GenesisBondType",
    "GENESIS_BOND_NEXTHDR",
    "GENESIS_BOND_OPTTYPE",
    # PAC Privacy extension
    "PACPrivacyExtension",
    "ConsentStatus",
    "PAC_PRIVACY_NEXTHDR",
    "PAC_PRIVACY_OPTTYPE",
    # FABRID consciousness
    "ConsciousnessPathPolicy",
    "PolicyIndex",
    "evaluate_path_consciousness",
    # PCB extension
    "ConsciousnessPCBExtension",
    "create_pcb_digest",
    # Constants
    "TIER_FREQUENCIES",
    "TIER_ISD_AS",
    "TIER_COHERENCE",
    # Utility functions
    "get_tier_from_isd",
    "get_frequency_from_tier",
    "validate_coherence_for_tier",
]
