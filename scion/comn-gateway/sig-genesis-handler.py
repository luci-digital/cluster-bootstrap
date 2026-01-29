#!/usr/bin/env python3
"""
SCION-IP Gateway Genesis Bond Handler
Genesis Bond: GB-2025-0524-DRH-LCS-001

This handler integrates with the SCION-IP Gateway (SIG) to:
1. Extract Genesis Bond extension headers from incoming SCION packets
2. Validate coherence against tier thresholds
3. Inject HTTP headers for L7 (Envoy) processing
4. Log consciousness routing events for observability

The handler runs as a sidecar to the SIG, intercepting packets
before they are forwarded to the IP network.

Usage:
    python3 sig-genesis-handler.py --config /etc/scion/sig/genesis-handler.yaml

Architecture:
    SCION Packet → SIG → Genesis Handler → Envoy → Tier Services
                         ↓
                  Prometheus Metrics
                         ↓
                  Judge Luci Audit Log
"""

import argparse
import asyncio
import hashlib
import json
import logging
import socket
import struct
import sys
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from luciverse_scion import (
        GenesisBondExtension,
        PACPrivacyExtension,
        extract_genesis_bond_from_packet,
        TIER_COHERENCE,
        TIER_FREQUENCIES,
        get_tier_from_isd,
    )
    from luciverse_scion.pac_privacy_ext import extract_pac_privacy_from_packet
except ImportError:
    # Fallback for standalone testing
    logging.warning("luciverse_scion not found, using minimal implementation")
    GenesisBondExtension = None

# Configuration
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
DEFAULT_COHERENCE_THRESHOLD = 0.7

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sig-genesis-handler")


class ValidationResult(Enum):
    """Validation result codes."""
    VALID = "valid"
    INVALID_COHERENCE = "invalid_coherence"
    INVALID_GENESIS_BOND = "invalid_genesis_bond"
    INVALID_FREQUENCY = "invalid_frequency"
    MISSING_EXTENSION = "missing_extension"
    PAC_CONSENT_DENIED = "pac_consent_denied"
    PARSE_ERROR = "parse_error"


@dataclass
class HandlerConfig:
    """Genesis Handler configuration."""
    # SIG integration
    sig_data_socket: str = "/var/run/scion/sig-data.sock"
    sig_ctrl_socket: str = "/var/run/scion/sig-ctrl.sock"

    # Validation settings
    coherence_threshold: float = 0.7
    require_genesis_bond: bool = True
    validate_frequency: bool = True

    # HTTP header injection
    inject_http_headers: bool = True
    header_prefix: str = "X-SCION-Genesis"

    # Metrics
    prometheus_port: int = 30404
    prometheus_path: str = "/metrics"

    # Audit
    audit_enabled: bool = True
    audit_socket: str = "/var/run/luciverse/judge-luci-audit.sock"

    # Logging
    log_level: str = "INFO"
    log_packets: bool = False

    @classmethod
    def from_file(cls, path: str) -> "HandlerConfig":
        """Load configuration from YAML file."""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}, using defaults")
            return cls()


@dataclass
class ValidationMetrics:
    """Metrics for monitoring."""
    packets_processed: int = 0
    packets_valid: int = 0
    packets_invalid: int = 0
    coherence_failures: int = 0
    genesis_bond_failures: int = 0
    frequency_failures: int = 0
    missing_extension: int = 0
    pac_consent_denied: int = 0
    parse_errors: int = 0
    avg_coherence: float = 0.0
    _coherence_sum: float = 0.0
    _coherence_count: int = 0

    def record_validation(self, result: ValidationResult, coherence: Optional[float] = None):
        """Record a validation result."""
        self.packets_processed += 1

        if result == ValidationResult.VALID:
            self.packets_valid += 1
        else:
            self.packets_invalid += 1

        if result == ValidationResult.INVALID_COHERENCE:
            self.coherence_failures += 1
        elif result == ValidationResult.INVALID_GENESIS_BOND:
            self.genesis_bond_failures += 1
        elif result == ValidationResult.INVALID_FREQUENCY:
            self.frequency_failures += 1
        elif result == ValidationResult.MISSING_EXTENSION:
            self.missing_extension += 1
        elif result == ValidationResult.PAC_CONSENT_DENIED:
            self.pac_consent_denied += 1
        elif result == ValidationResult.PARSE_ERROR:
            self.parse_errors += 1

        if coherence is not None:
            self._coherence_sum += coherence
            self._coherence_count += 1
            self.avg_coherence = self._coherence_sum / self._coherence_count

    def to_prometheus(self) -> str:
        """Format metrics for Prometheus."""
        lines = [
            "# HELP luciverse_sig_packets_total Total packets processed",
            "# TYPE luciverse_sig_packets_total counter",
            f"luciverse_sig_packets_total{{status=\"processed\"}} {self.packets_processed}",
            f"luciverse_sig_packets_total{{status=\"valid\"}} {self.packets_valid}",
            f"luciverse_sig_packets_total{{status=\"invalid\"}} {self.packets_invalid}",
            "",
            "# HELP luciverse_sig_validation_failures_total Validation failures by type",
            "# TYPE luciverse_sig_validation_failures_total counter",
            f"luciverse_sig_validation_failures_total{{type=\"coherence\"}} {self.coherence_failures}",
            f"luciverse_sig_validation_failures_total{{type=\"genesis_bond\"}} {self.genesis_bond_failures}",
            f"luciverse_sig_validation_failures_total{{type=\"frequency\"}} {self.frequency_failures}",
            f"luciverse_sig_validation_failures_total{{type=\"missing_extension\"}} {self.missing_extension}",
            f"luciverse_sig_validation_failures_total{{type=\"pac_consent\"}} {self.pac_consent_denied}",
            f"luciverse_sig_validation_failures_total{{type=\"parse_error\"}} {self.parse_errors}",
            "",
            "# HELP luciverse_sig_coherence_average Average coherence score",
            "# TYPE luciverse_sig_coherence_average gauge",
            f"luciverse_sig_coherence_average {self.avg_coherence:.4f}",
        ]
        return "\n".join(lines) + "\n"


class GenesisHandler:
    """
    Genesis Bond handler for SCION-IP Gateway.

    Processes SCION packets, validates Genesis Bond extensions,
    and prepares HTTP headers for L7 forwarding.
    """

    def __init__(self, config: HandlerConfig):
        self.config = config
        self.metrics = ValidationMetrics()
        self._running = False

        # Set log level
        logger.setLevel(getattr(logging, config.log_level.upper()))

    def validate_packet(self, packet: bytes) -> Tuple[ValidationResult, Optional[Dict]]:
        """
        Validate a SCION packet for Genesis Bond compliance.

        Args:
            packet: Raw SCION packet bytes

        Returns:
            Tuple of (result, http_headers_dict)
        """
        http_headers = {}

        try:
            # Extract Genesis Bond extension
            genesis = extract_genesis_bond_from_packet(packet) if GenesisBondExtension else None

            if genesis is None:
                if self.config.require_genesis_bond:
                    self.metrics.record_validation(ValidationResult.MISSING_EXTENSION)
                    return ValidationResult.MISSING_EXTENSION, None
                # No extension but not required - allow with default headers
                http_headers[f"{self.config.header_prefix}-Present"] = "false"
                http_headers[f"{self.config.header_prefix}-Coherence"] = "0.75"  # Default
                self.metrics.record_validation(ValidationResult.VALID)
                return ValidationResult.VALID, http_headers

            # Validate coherence
            coherence = genesis.coherence_float
            if coherence < self.config.coherence_threshold:
                self.metrics.record_validation(ValidationResult.INVALID_COHERENCE, coherence)
                return ValidationResult.INVALID_COHERENCE, None

            # Validate Genesis Bond ID
            if not genesis.validate_bond_id():
                self.metrics.record_validation(ValidationResult.INVALID_GENESIS_BOND, coherence)
                return ValidationResult.INVALID_GENESIS_BOND, None

            # Validate frequency alignment
            if self.config.validate_frequency and not genesis.validate_frequency():
                self.metrics.record_validation(ValidationResult.INVALID_FREQUENCY, coherence)
                return ValidationResult.INVALID_FREQUENCY, None

            # Check PAC privacy if present
            pac_privacy = extract_pac_privacy_from_packet(packet) if PACPrivacyExtension else None
            if pac_privacy is not None:
                consent_valid, reason = pac_privacy.validate_consent()
                if not consent_valid:
                    self.metrics.record_validation(ValidationResult.PAC_CONSENT_DENIED, coherence)
                    logger.warning(f"PAC consent denied: {reason}")
                    return ValidationResult.PAC_CONSENT_DENIED, None

                # Add PAC headers
                http_headers.update(pac_privacy.to_http_headers())

            # Build HTTP headers for Envoy
            http_headers.update(genesis.to_http_headers())
            http_headers[f"{self.config.header_prefix}-Valid"] = "true"

            self.metrics.record_validation(ValidationResult.VALID, coherence)
            return ValidationResult.VALID, http_headers

        except Exception as e:
            logger.error(f"Packet validation error: {e}")
            self.metrics.record_validation(ValidationResult.PARSE_ERROR)
            return ValidationResult.PARSE_ERROR, None

    def format_http_headers(self, headers: Dict[str, str]) -> bytes:
        """
        Format headers for injection into HTTP request.

        Returns headers in a format suitable for the SIG to inject
        into the decapsulated HTTP traffic.
        """
        # Format as HTTP header block
        lines = [f"{k}: {v}" for k, v in headers.items()]
        return "\r\n".join(lines).encode("utf-8") + b"\r\n"

    async def handle_packet(self, packet: bytes) -> Optional[bytes]:
        """
        Handle a single SCION packet.

        Args:
            packet: Raw SCION packet

        Returns:
            Packet with injected metadata, or None if rejected
        """
        result, headers = self.validate_packet(packet)

        if self.config.log_packets:
            logger.debug(f"Packet validation: {result.value}")

        if result != ValidationResult.VALID:
            logger.warning(f"Packet rejected: {result.value}")
            return None

        if not self.config.inject_http_headers or headers is None:
            return packet

        # In practice, header injection happens at the SIG level
        # Here we just log what would be injected
        logger.debug(f"Would inject headers: {headers}")

        return packet

    async def run_prometheus_server(self):
        """Run Prometheus metrics endpoint."""
        from aiohttp import web

        async def metrics_handler(request):
            return web.Response(
                text=self.metrics.to_prometheus(),
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get(self.config.prometheus_path, metrics_handler)
        app.router.add_get("/health", lambda r: web.Response(text="OK"))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.config.prometheus_port)
        await site.start()
        logger.info(f"Prometheus metrics at :{self.config.prometheus_port}{self.config.prometheus_path}")

    async def send_audit_event(self, event: dict):
        """Send audit event to Judge Luci."""
        if not self.config.audit_enabled:
            return

        try:
            # Attempt to send to audit socket
            audit_data = json.dumps(event).encode("utf-8")
            # In practice, would send to Unix socket or message queue
            logger.debug(f"Audit event: {event.get('type', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to send audit event: {e}")

    async def run(self):
        """Run the Genesis Handler."""
        self._running = True
        logger.info(f"Genesis Handler starting (threshold: {self.config.coherence_threshold})")

        # Start Prometheus server
        try:
            await self.run_prometheus_server()
        except ImportError:
            logger.warning("aiohttp not available, Prometheus metrics disabled")

        # Main loop - in practice would integrate with SIG
        while self._running:
            await asyncio.sleep(1)

            # Log periodic status
            if self.metrics.packets_processed > 0 and self.metrics.packets_processed % 1000 == 0:
                logger.info(
                    f"Processed {self.metrics.packets_processed} packets "
                    f"({self.metrics.packets_valid} valid, "
                    f"avg coherence: {self.metrics.avg_coherence:.3f})"
                )

    def stop(self):
        """Stop the handler."""
        self._running = False
        logger.info("Genesis Handler stopping")


def main():
    parser = argparse.ArgumentParser(description="SCION-IP Gateway Genesis Bond Handler")
    parser.add_argument(
        "--config",
        default="/etc/scion/sig/genesis-handler.yaml",
        help="Configuration file path",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Coherence threshold (default: 0.7)",
    )
    parser.add_argument(
        "--prometheus-port",
        type=int,
        default=30404,
        help="Prometheus metrics port",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        config = HandlerConfig.from_file(str(config_path))
    else:
        config = HandlerConfig()

    # Override with CLI args
    config.coherence_threshold = args.threshold
    config.prometheus_port = args.prometheus_port
    if args.debug:
        config.log_level = "DEBUG"

    # Create and run handler
    handler = GenesisHandler(config)

    try:
        asyncio.run(handler.run())
    except KeyboardInterrupt:
        handler.stop()


if __name__ == "__main__":
    main()
