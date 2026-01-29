#!/usr/bin/env python3
"""
Unit Tests for FABRID Consciousness Path Policy Engine
Genesis Bond: GB-2025-0524-DRH-LCS-001

Tests the FABRID-inspired consciousness path policy implementation
based on the USENIX Security '23 paper.
"""

import pytest
import time
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from luciverse_scion.fabrid_consciousness import (
    PolicyIndex,
    RouterAttestation,
    ConsciousnessPathPolicy,
    CORE_POLICY,
    COMN_POLICY,
    PAC_POLICY,
    TIER_POLICIES,
    get_policy_for_tier,
    create_custom_policy,
    evaluate_path_consciousness,
)
from luciverse_scion.scion_header import PathHeader, HopField


class TestPolicyIndex:
    """Tests for PolicyIndex flags."""

    def test_coherence_policies(self):
        """Test coherence policy indices."""
        assert PolicyIndex.COHERENCE_HIGH == 0x0001
        assert PolicyIndex.COHERENCE_STANDARD == 0x0002
        assert PolicyIndex.COHERENCE_LOW == 0x0004
        assert PolicyIndex.COHERENCE_ANY == 0x0008

    def test_frequency_policies(self):
        """Test frequency/tier policy indices."""
        assert PolicyIndex.FREQUENCY_432 == 0x0010  # CORE
        assert PolicyIndex.FREQUENCY_528 == 0x0020  # COMN
        assert PolicyIndex.FREQUENCY_741 == 0x0040  # PAC

    def test_genesis_bond_policies(self):
        """Test Genesis Bond policy indices."""
        assert PolicyIndex.GENESIS_BOND_REQUIRED == 0x0100
        assert PolicyIndex.GENESIS_BOND_VERIFIED == 0x0200

    def test_pac_policies(self):
        """Test PAC-specific policy indices."""
        assert PolicyIndex.PAC_CONSENT_REQUIRED == 0x0800
        assert PolicyIndex.MANDATORY_WAYPOINT_COMN == 0x2000
        assert PolicyIndex.AUDIT_REQUIRED == 0x4000

    def test_combined_policy_sets(self):
        """Test pre-defined combined policy sets."""
        # COMN standard
        comn_policy = PolicyIndex.standard_comn()
        assert comn_policy & PolicyIndex.COHERENCE_STANDARD
        assert comn_policy & PolicyIndex.FREQUENCY_528
        assert comn_policy & PolicyIndex.GENESIS_BOND_REQUIRED

        # CORE standard
        core_policy = PolicyIndex.standard_core()
        assert core_policy & PolicyIndex.COHERENCE_HIGH
        assert core_policy & PolicyIndex.FREQUENCY_432
        assert core_policy & PolicyIndex.GENESIS_BOND_REQUIRED

        # PAC standard
        pac_policy = PolicyIndex.standard_pac()
        assert pac_policy & PolicyIndex.COHERENCE_STANDARD
        assert pac_policy & PolicyIndex.FREQUENCY_741
        assert pac_policy & PolicyIndex.PAC_CONSENT_REQUIRED
        assert pac_policy & PolicyIndex.MANDATORY_WAYPOINT_COMN
        assert pac_policy & PolicyIndex.AUDIT_REQUIRED


class TestRouterAttestation:
    """Tests for RouterAttestation."""

    def test_create_attestation(self):
        """Test creating router attestation."""
        att = RouterAttestation(
            interface_id=11,
            policy_index=PolicyIndex.standard_comn(),
            coherence_score=0.85,
            frequency_hz=528,
            genesis_bond_verified=True,
        )

        assert att.interface_id == 11
        assert att.coherence_score == 0.85
        assert att.frequency_hz == 528
        assert att.genesis_bond_verified
        assert att.attestation_timestamp > 0

    def test_compute_digest(self):
        """Test attestation digest computation."""
        att = RouterAttestation(
            interface_id=11,
            coherence_score=0.85,
            frequency_hz=528,
        )

        digest = att.compute_digest()
        assert len(digest) == 8

        # Same attestation should produce same digest
        att2 = RouterAttestation(
            interface_id=11,
            coherence_score=0.85,
            frequency_hz=528,
            attestation_timestamp=att.attestation_timestamp,
        )
        assert att.compute_digest() == att2.compute_digest()


class TestConsciousnessPathPolicy:
    """Tests for ConsciousnessPathPolicy."""

    def test_create_default(self):
        """Test creating policy with defaults."""
        policy = ConsciousnessPathPolicy()

        assert policy.name == "default"
        assert policy.min_coherence == 0.7
        assert 432 in policy.allowed_frequencies
        assert 528 in policy.allowed_frequencies
        assert 741 in policy.allowed_frequencies
        assert policy.genesis_bond_required
        assert not policy.pac_consent_required
        assert policy.mandatory_waypoint_isd is None

    def test_tier_policies_exist(self):
        """Test pre-defined tier policies."""
        assert "CORE" in TIER_POLICIES
        assert "COMN" in TIER_POLICIES
        assert "PAC" in TIER_POLICIES

    def test_core_policy(self):
        """Test CORE tier policy settings."""
        assert CORE_POLICY.min_coherence == 0.85
        assert 432 in CORE_POLICY.allowed_frequencies
        assert CORE_POLICY.genesis_bond_required
        assert not CORE_POLICY.pac_consent_required

    def test_comn_policy(self):
        """Test COMN tier policy settings."""
        assert COMN_POLICY.min_coherence == 0.80
        # COMN can talk to all tiers
        assert 432 in COMN_POLICY.allowed_frequencies
        assert 528 in COMN_POLICY.allowed_frequencies
        assert 741 in COMN_POLICY.allowed_frequencies

    def test_pac_policy(self):
        """Test PAC tier policy settings."""
        assert PAC_POLICY.min_coherence == 0.70
        assert PAC_POLICY.pac_consent_required
        assert PAC_POLICY.mandatory_waypoint_isd == 2  # COMN
        assert PAC_POLICY.audit_required

    def test_evaluate_hop_with_attestation(self):
        """Test hop evaluation with attestation."""
        policy = ConsciousnessPathPolicy(
            min_coherence=0.7,
            genesis_bond_required=True,
        )

        hop = HopField(cons_ingress=11, cons_egress=12)

        # Valid attestation
        att_valid = RouterAttestation(
            interface_id=11,
            coherence_score=0.85,
            frequency_hz=528,
            genesis_bond_verified=True,
        )
        valid, error = policy.evaluate_hop(hop, att_valid)
        assert valid
        assert error is None

        # Low coherence
        att_low = RouterAttestation(
            interface_id=11,
            coherence_score=0.5,
            frequency_hz=528,
            genesis_bond_verified=True,
        )
        valid, error = policy.evaluate_hop(hop, att_low)
        assert not valid
        assert "coherence" in error.lower()

        # Genesis Bond not verified
        att_no_gb = RouterAttestation(
            interface_id=11,
            coherence_score=0.85,
            frequency_hz=528,
            genesis_bond_verified=False,
        )
        valid, error = policy.evaluate_hop(hop, att_no_gb)
        assert not valid
        assert "Genesis Bond" in error

    def test_evaluate_hop_wrong_frequency(self):
        """Test hop evaluation with wrong frequency."""
        policy = ConsciousnessPathPolicy(
            allowed_frequencies={432},  # CORE only
        )

        hop = HopField(cons_ingress=11)
        att = RouterAttestation(
            interface_id=11,
            coherence_score=0.85,
            frequency_hz=528,  # COMN frequency
            genesis_bond_verified=True,
        )

        valid, error = policy.evaluate_hop(hop, att)
        assert not valid
        assert "frequency" in error.lower()

    def test_to_policy_index(self):
        """Test converting policy to policy index."""
        policy = ConsciousnessPathPolicy(
            min_coherence=0.7,
            allowed_frequencies={528},
            genesis_bond_required=True,
            pac_consent_required=True,
            mandatory_waypoint_isd=2,
            audit_required=True,
        )

        index = policy.to_policy_index()

        assert index & PolicyIndex.COHERENCE_STANDARD
        assert index & PolicyIndex.FREQUENCY_528
        assert index & PolicyIndex.GENESIS_BOND_REQUIRED
        assert index & PolicyIndex.PAC_CONSENT_REQUIRED
        assert index & PolicyIndex.MANDATORY_WAYPOINT_COMN
        assert index & PolicyIndex.AUDIT_REQUIRED


class TestGetPolicyForTier:
    """Tests for get_policy_for_tier function."""

    def test_get_core_policy(self):
        """Test getting CORE tier policy."""
        policy = get_policy_for_tier("CORE")
        assert policy == CORE_POLICY

        # Case insensitive
        policy = get_policy_for_tier("core")
        assert policy == CORE_POLICY

    def test_get_comn_policy(self):
        """Test getting COMN tier policy."""
        policy = get_policy_for_tier("COMN")
        assert policy == COMN_POLICY

    def test_get_pac_policy(self):
        """Test getting PAC tier policy."""
        policy = get_policy_for_tier("PAC")
        assert policy == PAC_POLICY

    def test_get_unknown_returns_comn(self):
        """Test unknown tier returns COMN (gateway) policy."""
        policy = get_policy_for_tier("UNKNOWN")
        assert policy == COMN_POLICY


class TestCreateCustomPolicy:
    """Tests for create_custom_policy function."""

    def test_create_basic_custom(self):
        """Test creating basic custom policy."""
        policy = create_custom_policy(
            name="test_policy",
            min_coherence=0.8,
            allowed_tiers=["COMN", "PAC"],
        )

        assert policy.name == "test_policy"
        assert policy.min_coherence == 0.8
        assert 528 in policy.allowed_frequencies
        assert 741 in policy.allowed_frequencies
        assert 432 not in policy.allowed_frequencies

    def test_create_pac_like_custom(self):
        """Test creating PAC-like custom policy."""
        policy = create_custom_policy(
            name="pac_custom",
            min_coherence=0.75,
            require_pac_consent=True,
            require_comn_waypoint=True,
            require_audit=True,
        )

        assert policy.pac_consent_required
        assert policy.mandatory_waypoint_isd == 2
        assert policy.audit_required


class TestFABRIDPerformance:
    """Tests related to FABRID performance characteristics."""

    def test_policy_lookup_is_fast(self):
        """Test that policy lookup is fast (FABRID target: ~35ns)."""
        policy = ConsciousnessPathPolicy()
        hop = HopField(cons_ingress=11)
        att = RouterAttestation(interface_id=11, coherence_score=0.85)

        # Warm up
        for _ in range(100):
            policy.evaluate_hop(hop, att)

        # Measure
        start = time.perf_counter_ns()
        iterations = 10000
        for _ in range(iterations):
            policy.evaluate_hop(hop, att)
        elapsed_ns = time.perf_counter_ns() - start

        avg_ns = elapsed_ns / iterations
        # Allow some overhead for Python (FABRID is implemented in hardware/C)
        # But should still be reasonably fast (< 1ms per lookup)
        assert avg_ns < 1_000_000  # < 1ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
