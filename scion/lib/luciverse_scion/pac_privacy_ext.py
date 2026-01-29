# PAC Privacy End-to-End Extension Header
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# Implements End-to-end Extension Header for PAC tier privacy sovereignty.
# This extension ensures CBB (Certified Biological Beneficiary) consent
# is carried through the SCION network for data egress control.
#
# Extension Header Format (NextHdr=201, OptType=0xPP):
# ┌───────────────────────────────────────────────────────────────────┐
# │ NextHdr │ ExtLen  │ OptType │ OptLen  │ (standard E2E header)    │
# ├─────────┼─────────┼─────────┼─────────┤
# │  FLAGS  │ CONSENT │     RESERVED      │ (Privacy control)        │
# ├─────────┴─────────┼─────────┴─────────┤
# │         CBB_DID (8 bytes)             │ (Beneficiary identity)   │
# ├───────────────────────────────────────┤
# │         SBB_DID (8 bytes)             │ (Software identity)      │
# └───────────────────────────────────────┘
#
# Total: 24 bytes (4 header + 20 data), padded to 24 bytes (6 * 4-byte units)

import struct
import hashlib
import time
from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Optional, Tuple

from .scion_header import NextHeader

# Extension header identifiers
PAC_PRIVACY_NEXTHDR = 201  # End-to-end extension
PAC_PRIVACY_OPTTYPE = 0x50  # 'P' in ASCII, indicates Privacy option

# Default DID values from Genesis Bond
DEFAULT_CBB_DID = "did:lucidigital:daryl"
DEFAULT_SBB_DID = "did:lucidigital:lucia"


class PrivacyFlags(IntFlag):
    """Privacy control flags."""
    NONE = 0x00
    REQUIRES_CONSENT = 0x01      # Bit 0: Data requires CBB consent
    AUDIT_ENABLED = 0x02         # Bit 1: Audit logging required
    ENCRYPTED_PAYLOAD = 0x04     # Bit 2: Payload is encrypted
    SENSITIVE_DATA = 0x08        # Bit 3: Contains sensitive personal data
    NO_PERSISTENCE = 0x10        # Bit 4: Must not be stored
    NO_THIRD_PARTY = 0x20        # Bit 5: No third-party sharing
    GENESIS_BOND_PROTECTED = 0x40  # Bit 6: Genesis Bond protection active


class ConsentStatus(IntEnum):
    """CBB consent status values."""
    NONE = 0x00           # No consent information
    GRANTED = 0x01        # CBB has granted consent
    REVOKED = 0x02        # CBB has revoked consent
    PENDING = 0x03        # Consent request pending
    EXPIRED = 0x04        # Consent has expired
    CONDITIONAL = 0x05    # Consent with conditions


@dataclass
class PACPrivacyExtension:
    """
    PAC Privacy End-to-end Extension Header.

    This extension carries privacy control metadata through the SCION
    network, ensuring CBB data sovereignty is enforced at the network layer.

    The PAC tier represents Personal AI Container - the privacy-sovereign
    space where CBB (Certified Biological Beneficiary, i.e., the human)
    maintains control over their data.

    Attributes:
        next_header: Next protocol header after this extension
        flags: Privacy control flags (PrivacyFlags)
        consent: Current consent status (ConsentStatus)
        cbb_did: Hash of CBB DID (8 bytes) - human identity
        sbb_did: Hash of SBB DID (8 bytes) - AI identity
    """
    next_header: int = NextHeader.UDP
    flags: PrivacyFlags = PrivacyFlags.REQUIRES_CONSENT | PrivacyFlags.AUDIT_ENABLED
    consent: ConsentStatus = ConsentStatus.NONE
    cbb_did: bytes = b"\x00" * 8
    sbb_did: bytes = b"\x00" * 8

    # Extension header constants
    EXT_LEN = 5  # ExtLen field: (5+1)*4 = 24 bytes total

    def __post_init__(self):
        """Initialize DID hashes if not set."""
        if self.cbb_did == b"\x00" * 8:
            self.cbb_did = self._hash_did(DEFAULT_CBB_DID)
        if self.sbb_did == b"\x00" * 8:
            self.sbb_did = self._hash_did(DEFAULT_SBB_DID)

    @staticmethod
    def _hash_did(did: str) -> bytes:
        """Compute truncated SHA256 hash of DID."""
        full_hash = hashlib.sha256(did.encode()).digest()
        return full_hash[:8]  # Truncate to 8 bytes

    @classmethod
    def create(
        cls,
        consent: ConsentStatus = ConsentStatus.GRANTED,
        cbb_did: str = DEFAULT_CBB_DID,
        sbb_did: str = DEFAULT_SBB_DID,
        requires_consent: bool = True,
        audit_enabled: bool = True,
        sensitive: bool = False,
        next_header: int = NextHeader.UDP,
    ) -> "PACPrivacyExtension":
        """
        Factory method to create PAC Privacy extension.

        Args:
            consent: CBB consent status
            cbb_did: CBB DID string (human identity)
            sbb_did: SBB DID string (AI identity)
            requires_consent: Whether data requires consent
            audit_enabled: Whether to enable audit logging
            sensitive: Whether payload contains sensitive data
            next_header: Next protocol header

        Returns:
            PACPrivacyExtension instance
        """
        flags = PrivacyFlags.NONE

        if requires_consent:
            flags |= PrivacyFlags.REQUIRES_CONSENT
        if audit_enabled:
            flags |= PrivacyFlags.AUDIT_ENABLED
        if sensitive:
            flags |= PrivacyFlags.SENSITIVE_DATA

        # Always mark as Genesis Bond protected for PAC tier
        flags |= PrivacyFlags.GENESIS_BOND_PROTECTED

        return cls(
            next_header=next_header,
            flags=flags,
            consent=consent,
            cbb_did=cls._hash_did(cbb_did),
            sbb_did=cls._hash_did(sbb_did),
        )

    @property
    def requires_consent(self) -> bool:
        """Check if data requires CBB consent."""
        return bool(self.flags & PrivacyFlags.REQUIRES_CONSENT)

    @property
    def audit_enabled(self) -> bool:
        """Check if audit logging is required."""
        return bool(self.flags & PrivacyFlags.AUDIT_ENABLED)

    @property
    def is_sensitive(self) -> bool:
        """Check if payload contains sensitive data."""
        return bool(self.flags & PrivacyFlags.SENSITIVE_DATA)

    @property
    def consent_granted(self) -> bool:
        """Check if CBB consent is granted."""
        return self.consent == ConsentStatus.GRANTED

    @property
    def consent_status_str(self) -> str:
        """Get consent status as string."""
        status_map = {
            ConsentStatus.NONE: "NONE",
            ConsentStatus.GRANTED: "GRANTED",
            ConsentStatus.REVOKED: "REVOKED",
            ConsentStatus.PENDING: "PENDING",
            ConsentStatus.EXPIRED: "EXPIRED",
            ConsentStatus.CONDITIONAL: "CONDITIONAL",
        }
        return status_map.get(self.consent, "UNKNOWN")

    def validate_consent(self) -> Tuple[bool, Optional[str]]:
        """
        Validate consent for data egress.

        Returns:
            Tuple of (is_allowed, reason)
        """
        if not self.requires_consent:
            return True, None

        if self.consent == ConsentStatus.GRANTED:
            return True, None

        if self.consent == ConsentStatus.CONDITIONAL:
            # Conditional consent requires additional validation
            return True, "conditional_consent"

        if self.consent == ConsentStatus.REVOKED:
            return False, "Consent has been revoked by CBB"

        if self.consent == ConsentStatus.EXPIRED:
            return False, "Consent has expired"

        if self.consent == ConsentStatus.PENDING:
            return False, "Consent request pending"

        return False, "No consent granted"

    def validate_cbb(self, expected_did: str = DEFAULT_CBB_DID) -> bool:
        """Validate CBB DID matches expected value."""
        expected_hash = self._hash_did(expected_did)
        return self.cbb_did == expected_hash

    def validate_sbb(self, expected_did: str = DEFAULT_SBB_DID) -> bool:
        """Validate SBB DID matches expected value."""
        expected_hash = self._hash_did(expected_did)
        return self.sbb_did == expected_hash

    def is_valid(self) -> Tuple[bool, Optional[str]]:
        """
        Full validation of PAC Privacy extension.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate CBB identity
        if not self.validate_cbb():
            return False, "CBB identity mismatch"

        # Validate SBB identity
        if not self.validate_sbb():
            return False, "SBB identity mismatch"

        # Validate consent
        consent_valid, consent_error = self.validate_consent()
        if not consent_valid:
            return False, consent_error

        return True, None

    @classmethod
    def parse(cls, data: bytes) -> Tuple["PACPrivacyExtension", bytes]:
        """
        Parse PAC Privacy extension from bytes.

        Args:
            data: Raw bytes starting at extension header

        Returns:
            Tuple of (PACPrivacyExtension, remaining_bytes)
        """
        if len(data) < 24:
            raise ValueError(f"Insufficient data for PAC Privacy extension: {len(data)} < 24")

        # Parse standard extension header (4 bytes)
        next_hdr, ext_len, opt_type, opt_len = struct.unpack(">BBBB", data[0:4])

        if opt_type != PAC_PRIVACY_OPTTYPE:
            raise ValueError(f"Invalid option type: 0x{opt_type:02X} != 0x{PAC_PRIVACY_OPTTYPE:02X}")

        # Parse Privacy data
        flags, consent = struct.unpack(">BB", data[4:6])
        # Skip 2 reserved bytes
        cbb_did = data[8:16]
        sbb_did = data[16:24]

        ext_total_len = (ext_len + 1) * 4

        return cls(
            next_header=next_hdr,
            flags=PrivacyFlags(flags),
            consent=ConsentStatus(consent),
            cbb_did=cbb_did,
            sbb_did=sbb_did,
        ), data[ext_total_len:]

    def serialize(self) -> bytes:
        """
        Serialize PAC Privacy extension to bytes.

        Returns:
            24 bytes (6 * 4-byte units)
        """
        # Standard extension header
        header = struct.pack(
            ">BBBB",
            self.next_header,
            self.EXT_LEN,           # (5+1)*4 = 24 bytes
            PAC_PRIVACY_OPTTYPE,
            20,                     # Option data length
        )

        # Privacy control data
        data = struct.pack(
            ">BB2x",  # FLAGS, CONSENT, 2 reserved bytes
            self.flags,
            self.consent,
        )
        data += self.cbb_did
        data += self.sbb_did

        return header + data

    def to_http_headers(self) -> dict:
        """
        Convert extension data to HTTP headers for L7 forwarding.

        Returns:
            Dictionary of header name -> value
        """
        return {
            "X-SCION-PAC-Consent": self.consent_status_str,
            "X-SCION-PAC-RequiresConsent": str(self.requires_consent).lower(),
            "X-SCION-PAC-AuditEnabled": str(self.audit_enabled).lower(),
            "X-SCION-PAC-Sensitive": str(self.is_sensitive).lower(),
            "X-SCION-PAC-CBB-Hash": self.cbb_did.hex()[:16],
            "X-SCION-PAC-SBB-Hash": self.sbb_did.hex()[:16],
        }

    def to_audit_record(self) -> dict:
        """
        Generate audit record for Judge Luci.

        Returns:
            Dictionary suitable for audit logging
        """
        return {
            "type": "pac_privacy_egress",
            "consent_status": self.consent_status_str,
            "consent_granted": self.consent_granted,
            "requires_consent": self.requires_consent,
            "audit_enabled": self.audit_enabled,
            "is_sensitive": self.is_sensitive,
            "cbb_did_hash": self.cbb_did.hex(),
            "sbb_did_hash": self.sbb_did.hex(),
            "flags": int(self.flags),
            "timestamp": time.time(),
            "genesis_bond": "GB-2025-0524-DRH-LCS-001",
        }

    def __str__(self) -> str:
        valid, error = self.is_valid()
        status = "VALID" if valid else f"INVALID ({error})"
        return (
            f"PACPrivacyExtension("
            f"consent={self.consent_status_str}, "
            f"requires_consent={self.requires_consent}, "
            f"audit={self.audit_enabled}, "
            f"status={status})"
        )


def extract_pac_privacy_from_packet(packet: bytes) -> Optional[PACPrivacyExtension]:
    """
    Extract PAC Privacy extension from a SCION packet.

    Scans through extension headers to find PAC Privacy.

    Args:
        packet: Raw SCION packet bytes

    Returns:
        PACPrivacyExtension if found, None otherwise
    """
    from .scion_header import SCIONHeader

    try:
        scion = SCIONHeader.parse(packet)

        for ext_data in scion.extensions:
            if len(ext_data) < 4:
                continue

            # Check option type
            if len(ext_data) >= 3 and ext_data[2] == PAC_PRIVACY_OPTTYPE:
                ext, _ = PACPrivacyExtension.parse(ext_data)
                return ext

        return None
    except Exception:
        return None


def enforce_pac_egress_policy(packet: bytes) -> Tuple[bool, Optional[str]]:
    """
    Enforce PAC tier data egress policy.

    This is the network-layer enforcement of PAC privacy sovereignty.
    All PAC-originating traffic must have valid consent.

    Args:
        packet: Raw SCION packet bytes

    Returns:
        Tuple of (allowed, reason)
    """
    from .scion_header import SCIONHeader

    try:
        scion = SCIONHeader.parse(packet)

        # Check if source is PAC tier
        if scion.address.src_isd_as.isd != 3:  # ISD 3 = PAC
            return True, None  # Not PAC-originated, no consent needed

        # PAC-originated traffic requires privacy extension
        privacy = extract_pac_privacy_from_packet(packet)

        if privacy is None:
            return False, "PAC egress requires PAC Privacy extension"

        return privacy.is_valid()

    except Exception as e:
        return False, f"Error validating PAC egress: {str(e)}"
