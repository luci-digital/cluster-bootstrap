#!/usr/bin/env python3
"""
Unit Tests for Genesis Bond Extension Header
Genesis Bond: GB-2025-0524-DRH-LCS-001

Tests the Genesis Bond Hop-by-hop Extension Header implementation
for SCION dataplane integration.
"""

import pytest
import struct
import time
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from luciverse_scion.genesis_bond_ext import (
    GenesisBondExtension,
    GenesisBondType,
    GENESIS_BOND_ID,
    GENESIS_BOND_NEXTHDR,
    GENESIS_BOND_OPTTYPE,
    extract_genesis_bond_from_packet,
    inject_genesis_bond_extension,
)
from luciverse_scion.scion_header import NextHeader


class TestGenesisBondExtension:
    """Tests for GenesisBondExtension class."""

    def test_create_default(self):
        """Test creating extension with defaults."""
        ext = GenesisBondExtension()

        assert ext.tier_type == GenesisBondType.COMN
        assert ext.frequency == 528
        assert ext.coherence == 178  # ~0.7
        assert len(ext.bond_id) == 8
        assert ext.timestamp > 0

    def test_create_from_tier(self):
        """Test factory method for creating extensions."""
        # CORE tier
        core_ext = GenesisBondExtension.create(tier="CORE", coherence=0.9)
        assert core_ext.tier_type == GenesisBondType.CORE
        assert core_ext.frequency == 432
        assert core_ext.coherence_float >= 0.89  # ~0.9

        # COMN tier
        comn_ext = GenesisBondExtension.create(tier="COMN", coherence=0.8)
        assert comn_ext.tier_type == GenesisBondType.COMN
        assert comn_ext.frequency == 528

        # PAC tier
        pac_ext = GenesisBondExtension.create(tier="PAC", coherence=0.75)
        assert pac_ext.tier_type == GenesisBondType.PAC
        assert pac_ext.frequency == 741

    def test_coherence_conversion(self):
        """Test coherence float/byte conversion."""
        ext = GenesisBondExtension.create(tier="COMN", coherence=0.85)

        # Byte value should be ~217 (0.85 * 255)
        assert 215 <= ext.coherence <= 220

        # Float conversion should be close to original
        assert 0.84 <= ext.coherence_float <= 0.86

    def test_tier_name(self):
        """Test tier name property."""
        ext_core = GenesisBondExtension(tier_type=GenesisBondType.CORE)
        assert ext_core.tier_name == "CORE"

        ext_comn = GenesisBondExtension(tier_type=GenesisBondType.COMN)
        assert ext_comn.tier_name == "COMN"

        ext_pac = GenesisBondExtension(tier_type=GenesisBondType.PAC)
        assert ext_pac.tier_name == "PAC"

    def test_validate_coherence(self):
        """Test coherence threshold validation."""
        # Above threshold
        ext_high = GenesisBondExtension.create(tier="COMN", coherence=0.85)
        assert ext_high.validate_coherence(0.7)
        assert ext_high.validate_coherence(0.8)
        assert not ext_high.validate_coherence(0.9)

        # Below threshold
        ext_low = GenesisBondExtension.create(tier="COMN", coherence=0.5)
        assert not ext_low.validate_coherence(0.7)

    def test_validate_bond_id(self):
        """Test Genesis Bond ID validation."""
        ext = GenesisBondExtension.create(tier="COMN", coherence=0.8)
        assert ext.validate_bond_id()

        # Invalid bond ID
        ext.bond_id = b"\x00" * 8
        assert not ext.validate_bond_id()

    def test_validate_frequency(self):
        """Test frequency alignment validation."""
        # Correct frequency
        ext_core = GenesisBondExtension(tier_type=GenesisBondType.CORE, frequency=432)
        assert ext_core.validate_frequency()

        # Wrong frequency
        ext_wrong = GenesisBondExtension(tier_type=GenesisBondType.CORE, frequency=528)
        assert not ext_wrong.validate_frequency()

    def test_is_valid_full(self):
        """Test full validation."""
        # Valid extension
        ext_valid = GenesisBondExtension.create(tier="COMN", coherence=0.85)
        is_valid, error = ext_valid.is_valid(0.7)
        assert is_valid
        assert error is None

        # Invalid coherence
        ext_low = GenesisBondExtension.create(tier="COMN", coherence=0.5)
        is_valid, error = ext_low.is_valid(0.7)
        assert not is_valid
        assert "Coherence" in error

    def test_serialize_deserialize(self):
        """Test serialization round-trip."""
        original = GenesisBondExtension.create(tier="PAC", coherence=0.75)
        original.timestamp = 1700000000  # Fixed timestamp for comparison

        # Serialize
        data = original.serialize()
        assert len(data) == 20  # 4 header + 16 data

        # Deserialize
        parsed, remaining = GenesisBondExtension.parse(data)

        assert parsed.tier_type == original.tier_type
        assert parsed.frequency == original.frequency
        assert abs(parsed.coherence - original.coherence) <= 1  # Allow rounding
        assert parsed.bond_id == original.bond_id
        assert parsed.timestamp == original.timestamp

    def test_to_http_headers(self):
        """Test HTTP header conversion."""
        ext = GenesisBondExtension.create(tier="COMN", coherence=0.85)
        headers = ext.to_http_headers()

        assert "X-SCION-Genesis-Bond" in headers
        assert headers["X-SCION-Genesis-Bond"] == GENESIS_BOND_ID
        assert "X-SCION-Genesis-Coherence" in headers
        assert "X-SCION-Genesis-Tier" in headers
        assert headers["X-SCION-Genesis-Tier"] == "COMN"
        assert "X-SCION-Genesis-Frequency" in headers
        assert headers["X-SCION-Genesis-Frequency"] == "528"

    def test_parse_invalid_opttype(self):
        """Test parsing with invalid option type."""
        # Create data with wrong option type
        data = struct.pack(">BBBB", NextHeader.UDP, 4, 0xFF, 16)
        data += b"\x00" * 16

        with pytest.raises(ValueError) as excinfo:
            GenesisBondExtension.parse(data)

        assert "Invalid option type" in str(excinfo.value)

    def test_parse_insufficient_data(self):
        """Test parsing with insufficient data."""
        with pytest.raises(ValueError) as excinfo:
            GenesisBondExtension.parse(b"\x00" * 10)

        assert "Insufficient data" in str(excinfo.value)


class TestGenesisBondTypeEnum:
    """Tests for GenesisBondType enum."""

    def test_tier_values(self):
        """Test tier type values."""
        assert GenesisBondType.CORE == 0x01
        assert GenesisBondType.COMN == 0x02
        assert GenesisBondType.PAC == 0x03


class TestExtractFromPacket:
    """Tests for packet extraction."""

    def test_extract_from_empty_returns_none(self):
        """Test extraction from empty/invalid packet."""
        result = extract_genesis_bond_from_packet(b"")
        assert result is None

    def test_extract_nonexistent_returns_none(self):
        """Test extraction when no Genesis Bond extension exists."""
        # Minimal valid SCION header without extension
        fake_packet = b"\x00" * 100
        result = extract_genesis_bond_from_packet(fake_packet)
        # May return None or raise - either is acceptable
        assert result is None


class TestConstants:
    """Tests for module constants."""

    def test_genesis_bond_id(self):
        """Test Genesis Bond ID constant."""
        assert GENESIS_BOND_ID == "GB-2025-0524-DRH-LCS-001"

    def test_nexthdr_value(self):
        """Test NextHdr value for Genesis Bond."""
        assert GENESIS_BOND_NEXTHDR == 200

    def test_opttype_value(self):
        """Test OptType value for Genesis Bond."""
        assert GENESIS_BOND_OPTTYPE == 0x47  # 'G'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
