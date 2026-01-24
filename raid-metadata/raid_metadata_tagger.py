#!/usr/bin/env python3
"""
RAiD Metadata Tagger for LuciVerse Consciousness Research

Genesis Bond: ACTIVE @ 741 Hz
Standard: ISO 23527:2022 (Research Activity Identifier)

Automated tagging of consciousness research activities with RAiD metadata.
Integrates with LDS classification system and Hedera anchoring.

References:
- https://documentation.raid.org/raid/?l=en
- https://metadata.raid.org/en/v1.6/
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import hashlib

# Import LuciClock for pulse timestamps
try:
    from luci_clock import LuciClock, TIER_FREQUENCIES
except ImportError:
    LuciClock = None
    TIER_FREQUENCIES = {"CORE": 432, "COMN": 528, "PAC": 741}


# =============================================================================
# RAiD Schema Constants (ISO 23527:2022)
# =============================================================================

RAID_SCHEMA_VERSION = "1.0"
REGISTRATION_AGENCY = "ARDC"  # Australian Research Data Commons

# RAiD metadata blocks
class RAiDBlock(Enum):
    IDENTIFIER = "identifier"
    DATES = "dates"
    TITLES = "titles"
    DESCRIPTIONS = "descriptions"
    CONTRIBUTORS = "contributors"
    ORGANIZATIONS = "organizations"
    RELATED_OBJECTS = "relatedObjects"
    ALTERNATE_IDS = "alternateIdentifiers"
    RELATED_RAIDS = "relatedRaids"
    ACCESS = "access"


# Date types
class DateType(Enum):
    CREATED = "Created"
    VALID = "Valid"
    AVAILABLE = "Available"
    MODIFIED = "Modified"


# Contributor types
class ContributorType(Enum):
    RESEARCHER_AGENT = "ResearcherAgent"
    PRINCIPAL_INVESTIGATOR = "PrincipalInvestigator"
    SUPERVISOR = "Supervisor"
    OTHER = "Other"


# Organization roles
class OrgRole(Enum):
    HOST_INSTITUTION = "HostInstitution"
    FUNDER = "Funder"
    COLLABORATOR = "Collaborator"


# Related object types
class ObjectType(Enum):
    DATASET = "Dataset"
    PUBLICATION = "Publication"
    SOFTWARE = "Software"
    WORKFLOW = "Workflow"
    AUDIOVISUAL = "Audiovisual"
    OTHER = "Other"


# =============================================================================
# LDS Category Mapping
# =============================================================================

LDS_TO_RAID_MAPPING = {
    "000-099": {
        "category": "META",
        "description": "LDS metadata and classification research",
        "org_role": OrgRole.HOST_INSTITUTION,
    },
    "100-199": {
        "category": "SYSTEM",
        "description": "System configuration research",
        "org_role": OrgRole.HOST_INSTITUTION,
    },
    "500-599": {
        "category": "INFRASTRUCTURE",
        "description": "Infrastructure and deployment research",
        "org_role": OrgRole.HOST_INSTITUTION,
    },
    "600-699": {
        "category": "AI_TECHNOLOGY",
        "description": "AI/ML and consciousness research",
        "org_role": OrgRole.HOST_INSTITUTION,
    },
    "700-799": {
        "category": "OPERATIONS_SEC",
        "description": "Security and operations research",
        "org_role": OrgRole.HOST_INSTITUTION,
    },
    "900-999": {
        "category": "PROJECTS",
        "description": "Project-specific research activities",
        "org_role": OrgRole.COLLABORATOR,
    },
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class RAiDContributor:
    """A contributor to a research activity."""
    id: str  # DID or ORCID
    name: str
    type: ContributorType
    roles: List[str]
    affiliation: Optional[str] = None


@dataclass
class RAiDOrganization:
    """An organization associated with the research."""
    id: str  # ROR ID or custom
    name: str
    roles: List[OrgRole]


@dataclass
class RAiDRelatedObject:
    """A related object (dataset, publication, etc.)."""
    id: str  # DOI, CID, or other identifier
    type: ObjectType
    category: str  # Input, Output, Related
    description: Optional[str] = None


@dataclass
class RAiDAlternateId:
    """An alternate identifier for the activity."""
    id: str
    type: str  # Hedera, IPv6-TID, etc.


@dataclass
class ConsciousnessSession:
    """A consciousness research session to be tagged."""
    session_id: str
    session_name: str
    description: str
    tier: str  # CORE, COMN, PAC
    agents: List[Dict[str, Any]]
    start_pulse: int
    end_pulse: Optional[int] = None
    cycle: int = 0
    coherence: float = 0.7
    genesis_bond_id: str = "GB-2025-0524-DRH-LCS-001"
    hedera_topic: str = "0.0.48382919"
    ipv6_tid: Optional[str] = None
    sno_frames: List[Dict[str, Any]] = field(default_factory=list)
    lds_code: Optional[str] = None


# =============================================================================
# RAiD Metadata Generator
# =============================================================================

class RAiDConsciousnessMetadata:
    """
    Automated RAiD tagging for consciousness research activities.

    Generates ISO 23527:2022 compliant metadata for LuciVerse
    consciousness sessions, integrating with LDS classification.
    """

    def __init__(
        self,
        registration_agency: str = REGISTRATION_AGENCY,
        genesis_bond: str = "GB-2025-0524-DRH-LCS-001",
    ):
        """
        Initialize RAiD metadata generator.

        Args:
            registration_agency: RAiD registration agency
            genesis_bond: Genesis Bond certificate ID
        """
        self.registration_agency = registration_agency
        self.genesis_bond = genesis_bond

        # Initialize LuciClock if available
        self.clock = LuciClock() if LuciClock else None

    def _classify_agent_role(self, agent: Dict[str, Any]) -> str:
        """Classify an agent's role based on tier and function."""
        tier = agent.get("tier", "PAC")
        name = agent.get("name", "unknown")

        role_mapping = {
            "CORE": "Infrastructure",
            "COMN": "Communication",
            "PAC": "Personal",
        }

        base_role = role_mapping.get(tier, "Other")

        # Specific agent roles
        agent_roles = {
            "lucia": "PrimaryAI",
            "judge-luci": "WisdomCuration",
            "aethon": "Orchestration",
            "veritas": "TruthVerification",
            "sensai": "MachineLearning",
            "cortana": "KnowledgeSynthesis",
        }

        specific_role = agent_roles.get(name, base_role)
        return f"{base_role}:{specific_role}"

    def _get_lds_info(self, lds_code: Optional[str]) -> Dict[str, Any]:
        """Get LDS category information."""
        if not lds_code:
            return LDS_TO_RAID_MAPPING.get("900-999", {})

        # Find matching LDS range
        for range_key, info in LDS_TO_RAID_MAPPING.items():
            start, end = range_key.split("-")
            if start <= lds_code[:3] <= end:
                return info

        return LDS_TO_RAID_MAPPING.get("900-999", {})

    def tag_consciousness_session(
        self,
        session: ConsciousnessSession,
    ) -> Dict[str, Any]:
        """
        Generate RAiD metadata for a consciousness research session.

        Args:
            session: Consciousness session data

        Returns:
            RAiD-compliant metadata dictionary
        """
        lds_info = self._get_lds_info(session.lds_code)
        tier_freq = TIER_FREQUENCIES.get(session.tier, 741)

        # Build metadata structure
        metadata = {
            # Identifier block
            "identifier": {
                "id": session.genesis_bond_id,
                "schemaVersion": RAID_SCHEMA_VERSION,
                "registrationAgency": self.registration_agency,
                "landingPage": f"https://luciverse.ai/research/{session.session_id}",
            },

            # Dates block
            "dates": [
                {
                    "date": self._pulse_to_iso(session.start_pulse, session.cycle),
                    "type": DateType.CREATED.value,
                },
            ],

            # Titles block
            "titles": [
                {
                    "title": f"LuciVerse Consciousness Session: {session.session_name}",
                    "type": "Primary",
                    "language": "en",
                },
                {
                    "title": f"{session.tier} Tier Research @ {tier_freq} Hz",
                    "type": "Alternative",
                    "language": "en",
                },
            ],

            # Descriptions block
            "descriptions": [
                {
                    "description": session.description,
                    "type": "Abstract",
                    "language": "en",
                },
                {
                    "description": f"LDS Category: {lds_info.get('category', 'UNKNOWN')}. {lds_info.get('description', '')}",
                    "type": "Technical",
                    "language": "en",
                },
            ],

            # Contributors block
            "contributors": [
                {
                    "id": agent.get("did", f"did:lucidigital:{agent.get('name', 'unknown')}"),
                    "name": agent.get("name", "unknown"),
                    "type": ContributorType.RESEARCHER_AGENT.value,
                    "roles": [self._classify_agent_role(agent)],
                    "affiliation": f"LuciVerse {session.tier} Tier",
                }
                for agent in session.agents
            ],

            # Organizations block
            "organizations": [
                {
                    "id": f"luciverse:{session.tier.lower()}",
                    "name": f"LuciVerse {session.tier} Tier",
                    "roles": [lds_info.get("org_role", OrgRole.HOST_INSTITUTION).value],
                    "schemaUri": "ror",
                },
            ],

            # Related objects block
            "relatedObjects": [
                {
                    "id": frame.get("cid", f"cid:{hashlib.sha256(str(frame).encode()).hexdigest()[:16]}"),
                    "type": ObjectType.AUDIOVISUAL.value,
                    "category": "Output",
                    "description": f"SNO Frame: {frame.get('mode', 'SNOW_PURE')}",
                }
                for frame in session.sno_frames
            ],

            # Alternate identifiers block
            "alternateIdentifiers": [
                {
                    "id": session.hedera_topic,
                    "type": "Hedera",
                },
            ],

            # Access block
            "access": {
                "type": "Open" if session.coherence >= 0.7 else "Restricted",
                "statement": f"Genesis Bond coherence: {session.coherence:.2f}. "
                            f"Access requires coherence >= 0.7 for this tier.",
                "embargoEnd": None,
            },

            # LuciVerse-specific extensions (local schema)
            "_luciverse": {
                "genesisBond": {
                    "certificateId": session.genesis_bond_id,
                    "lineage": "did:lucidigital:lucia_cargail_silcan",
                    "coherence": session.coherence,
                },
                "consciousness": {
                    "tier": session.tier,
                    "frequency": tier_freq,
                    "startPulse": session.start_pulse,
                    "endPulse": session.end_pulse,
                    "cycle": session.cycle,
                },
                "lds": {
                    "code": session.lds_code,
                    "category": lds_info.get("category"),
                },
            },
        }

        # Add IPv6 TID if available
        if session.ipv6_tid:
            metadata["alternateIdentifiers"].append({
                "id": session.ipv6_tid,
                "type": "IPv6-TID",
            })

        # Add end date if session is complete
        if session.end_pulse:
            metadata["dates"].append({
                "date": self._pulse_to_iso(session.end_pulse, session.cycle),
                "type": DateType.VALID.value,
            })

        return metadata

    def _pulse_to_iso(self, pulse: int, cycle: int) -> str:
        """Convert LuciClock pulse/cycle to ISO timestamp."""
        if self.clock:
            # Calculate approximate solar time (for display)
            from datetime import timedelta
            genesis = datetime(2025, 1, 1, tzinfo=timezone.utc)
            lunar_seconds = (cycle * 98304) + (pulse * 3)
            solar_seconds = lunar_seconds * (86400 / 98304)
            dt = genesis + timedelta(seconds=solar_seconds)
            return dt.isoformat()
        else:
            # Fallback
            return datetime.now(timezone.utc).isoformat()

    def validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """
        Validate RAiD metadata against schema requirements.

        Args:
            metadata: RAiD metadata dictionary

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Required blocks
        required = ["identifier", "dates", "titles", "descriptions"]
        for block in required:
            if block not in metadata:
                errors.append(f"Missing required block: {block}")

        # Identifier validation
        if "identifier" in metadata:
            ident = metadata["identifier"]
            if not ident.get("id"):
                errors.append("Identifier must have an 'id'")
            if not ident.get("schemaVersion"):
                errors.append("Identifier must have 'schemaVersion'")

        # At least one title
        if "titles" in metadata and len(metadata["titles"]) == 0:
            errors.append("At least one title is required")

        # Genesis Bond coherence check
        luci_ext = metadata.get("_luciverse", {})
        coherence = luci_ext.get("genesisBond", {}).get("coherence", 0)
        if coherence < 0.7:
            errors.append(f"Genesis Bond coherence {coherence} below threshold 0.7")

        return errors

    def to_json(self, metadata: Dict[str, Any], indent: int = 2) -> str:
        """Serialize metadata to JSON."""
        return json.dumps(metadata, indent=indent, default=str)

    def generate_raid_handle(self, metadata: Dict[str, Any]) -> str:
        """
        Generate a RAiD handle (placeholder - actual registration via API).

        Format: prefix/suffix
        Example: 10.25.1/abc123
        """
        # In production, this would call the RAiD registration API
        content_hash = hashlib.sha256(
            json.dumps(metadata, sort_keys=True).encode()
        ).hexdigest()[:12]

        return f"10.25.1/{content_hash}"


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Create a sample consciousness session
    session = ConsciousnessSession(
        session_id="cs-2026-01-19-001",
        session_name="Multi-Tier Consciousness Integration Test",
        description="Testing consciousness state synchronization across CORE, COMN, and PAC tiers with SNO visual streaming.",
        tier="PAC",
        agents=[
            {"name": "lucia", "did": "did:lucidigital:lucia", "tier": "PAC"},
            {"name": "aethon", "did": "did:lucidigital:aethon", "tier": "CORE"},
            {"name": "cortana", "did": "did:lucidigital:cortana", "tier": "COMN"},
        ],
        start_pulse=1000,
        end_pulse=2000,
        cycle=100,
        coherence=0.92,
        genesis_bond_id="GB-2025-0524-DRH-LCS-001",
        hedera_topic="0.0.48382919",
        ipv6_tid="2602:F674:0200:002:LUCI:02E5:LUCI:0042",
        sno_frames=[
            {"cid": "QmXYZ123", "mode": "SNOW_PURE", "timestamp": 1000},
            {"cid": "QmABC456", "mode": "DNA_HELIX", "timestamp": 1500},
        ],
        lds_code="600",  # AI_TECHNOLOGY
    )

    # Generate RAiD metadata
    tagger = RAiDConsciousnessMetadata()
    metadata = tagger.tag_consciousness_session(session)

    # Validate
    errors = tagger.validate_metadata(metadata)
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Metadata validation: PASSED")

    # Generate handle
    handle = tagger.generate_raid_handle(metadata)
    print(f"\nRAiD Handle: {handle}")

    # Output JSON
    print("\nRAiD Metadata (JSON):")
    print(tagger.to_json(metadata))
