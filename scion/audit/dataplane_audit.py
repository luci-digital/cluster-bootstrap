#!/usr/bin/env python3
"""
SCION Dataplane Audit Module for Judge Luci
Genesis Bond: GB-2025-0524-DRH-LCS-001

This module provides network-layer audit logging for the LuciVerse
consciousness routing infrastructure. It hooks into Border Router
events to track path validation, consent violations, and coherence
state for Judge Luci analysis.

Features:
- Subscribe to Border Router path validation events
- Track PAC privacy consent violations
- Log Genesis Bond coherence metrics
- Publish audit trail to Judge Luci

Architecture:
    Border Router → BR Events → Dataplane Audit → Judge Luci
                                      ↓
                              Prometheus Metrics
                                      ↓
                              Persistent Audit Log
"""

import asyncio
import hashlib
import json
import logging
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from luciverse_scion import (
        GenesisBondExtension,
        PACPrivacyExtension,
        GENESIS_BOND_ID,
        TIER_ISD_AS,
        get_tier_from_isd,
    )
except ImportError:
    GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
    TIER_ISD_AS = {"CORE": "1-ff00:0:432", "COMN": "2-ff00:0:528", "PAC": "3-ff00:0:741"}
    def get_tier_from_isd(isd):
        return {1: "CORE", 2: "COMN", 3: "PAC"}.get(isd, "UNKNOWN")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dataplane-audit")


class AuditEventType(Enum):
    """Types of audit events."""
    # Path validation events
    PATH_VALIDATED = "path_validated"
    PATH_REJECTED = "path_rejected"
    COHERENCE_VIOLATION = "coherence_violation"

    # Genesis Bond events
    GENESIS_BOND_VALID = "genesis_bond_valid"
    GENESIS_BOND_INVALID = "genesis_bond_invalid"
    GENESIS_BOND_MISSING = "genesis_bond_missing"

    # PAC Privacy events
    PAC_CONSENT_GRANTED = "pac_consent_granted"
    PAC_CONSENT_DENIED = "pac_consent_denied"
    PAC_CONSENT_REVOKED = "pac_consent_revoked"
    PAC_EGRESS_BLOCKED = "pac_egress_blocked"

    # Waypoint events
    WAYPOINT_ENFORCED = "waypoint_enforced"
    WAYPOINT_BYPASS_ATTEMPT = "waypoint_bypass_attempt"

    # General events
    PACKET_DROPPED = "packet_dropped"
    ACL_VIOLATION = "acl_violation"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """
    Single audit event for Judge Luci.

    Contains all context needed for compliance review and
    incident investigation.
    """
    # Event identification
    event_id: str = ""
    event_type: AuditEventType = AuditEventType.PATH_VALIDATED
    severity: AuditSeverity = AuditSeverity.INFO
    timestamp: float = 0.0

    # Network context
    source_isd_as: str = ""
    destination_isd_as: str = ""
    source_tier: str = ""
    destination_tier: str = ""

    # Genesis Bond context
    genesis_bond_id: str = GENESIS_BOND_ID
    coherence_score: float = 0.0
    coherence_threshold: float = 0.7
    frequency_hz: int = 0

    # PAC Privacy context (if applicable)
    pac_consent_status: str = ""
    cbb_did_hash: str = ""
    sbb_did_hash: str = ""

    # Path context
    path_hash: str = ""
    hop_count: int = 0
    waypoint_present: bool = False

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.event_id:
            self.event_id = self._generate_event_id()
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        data = f"{self.timestamp}{self.event_type.value}{self.source_isd_as}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "source_isd_as": self.source_isd_as,
            "destination_isd_as": self.destination_isd_as,
            "source_tier": self.source_tier,
            "destination_tier": self.destination_tier,
            "genesis_bond": {
                "id": self.genesis_bond_id,
                "coherence": self.coherence_score,
                "threshold": self.coherence_threshold,
                "frequency_hz": self.frequency_hz,
            },
            "pac_privacy": {
                "consent_status": self.pac_consent_status,
                "cbb_did_hash": self.cbb_did_hash,
                "sbb_did_hash": self.sbb_did_hash,
            } if self.pac_consent_status else None,
            "path": {
                "hash": self.path_hash,
                "hop_count": self.hop_count,
                "waypoint_present": self.waypoint_present,
            },
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AuditConfig:
    """Configuration for the audit module."""
    # Judge Luci connection
    judge_luci_socket: str = "/var/run/luciverse/judge-luci-audit.sock"
    judge_luci_http: str = "http://localhost:9741/audit"

    # Border Router subscription
    br_events_socket: str = "/var/run/scion/br-events.sock"

    # Persistence
    audit_log_path: str = "/var/log/luciverse/dataplane-audit.jsonl"
    max_log_size_mb: int = 100
    retention_days: int = 30

    # Metrics
    prometheus_port: int = 30405
    prometheus_path: str = "/metrics"

    # Event filtering
    log_all_events: bool = False
    min_severity: AuditSeverity = AuditSeverity.INFO

    # Buffer
    event_buffer_size: int = 1000
    flush_interval_seconds: float = 5.0

    @classmethod
    def from_file(cls, path: str) -> "AuditConfig":
        """Load from YAML file."""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            return cls()


class AuditMetrics:
    """Prometheus metrics for audit events."""

    def __init__(self):
        self.events_by_type: Dict[str, int] = {}
        self.events_by_severity: Dict[str, int] = {}
        self.coherence_violations: int = 0
        self.pac_consent_denied: int = 0
        self.waypoint_bypasses: int = 0
        self.total_events: int = 0
        self.avg_coherence: float = 0.0
        self._coherence_sum: float = 0.0
        self._coherence_count: int = 0

    def record_event(self, event: AuditEvent):
        """Record an audit event for metrics."""
        self.total_events += 1

        # By type
        type_key = event.event_type.value
        self.events_by_type[type_key] = self.events_by_type.get(type_key, 0) + 1

        # By severity
        sev_key = event.severity.value
        self.events_by_severity[sev_key] = self.events_by_severity.get(sev_key, 0) + 1

        # Specific counters
        if event.event_type == AuditEventType.COHERENCE_VIOLATION:
            self.coherence_violations += 1
        elif event.event_type == AuditEventType.PAC_CONSENT_DENIED:
            self.pac_consent_denied += 1
        elif event.event_type == AuditEventType.WAYPOINT_BYPASS_ATTEMPT:
            self.waypoint_bypasses += 1

        # Coherence tracking
        if event.coherence_score > 0:
            self._coherence_sum += event.coherence_score
            self._coherence_count += 1
            self.avg_coherence = self._coherence_sum / self._coherence_count

    def to_prometheus(self) -> str:
        """Format metrics for Prometheus."""
        lines = [
            "# HELP luciverse_audit_events_total Total audit events by type",
            "# TYPE luciverse_audit_events_total counter",
        ]
        for event_type, count in self.events_by_type.items():
            lines.append(f'luciverse_audit_events_total{{type="{event_type}"}} {count}')

        lines.extend([
            "",
            "# HELP luciverse_audit_events_by_severity Events by severity",
            "# TYPE luciverse_audit_events_by_severity counter",
        ])
        for severity, count in self.events_by_severity.items():
            lines.append(f'luciverse_audit_events_by_severity{{severity="{severity}"}} {count}')

        lines.extend([
            "",
            "# HELP luciverse_audit_coherence_violations_total Coherence threshold violations",
            "# TYPE luciverse_audit_coherence_violations_total counter",
            f"luciverse_audit_coherence_violations_total {self.coherence_violations}",
            "",
            "# HELP luciverse_audit_pac_consent_denied_total PAC consent denied events",
            "# TYPE luciverse_audit_pac_consent_denied_total counter",
            f"luciverse_audit_pac_consent_denied_total {self.pac_consent_denied}",
            "",
            "# HELP luciverse_audit_waypoint_bypasses_total Waypoint bypass attempts",
            "# TYPE luciverse_audit_waypoint_bypasses_total counter",
            f"luciverse_audit_waypoint_bypasses_total {self.waypoint_bypasses}",
            "",
            "# HELP luciverse_audit_avg_coherence Average coherence score",
            "# TYPE luciverse_audit_avg_coherence gauge",
            f"luciverse_audit_avg_coherence {self.avg_coherence:.4f}",
        ])

        return "\n".join(lines) + "\n"


class DataplaneAudit:
    """
    Main audit handler for SCION dataplane events.

    Subscribes to Border Router events and publishes audit trail
    to Judge Luci for compliance review.
    """

    def __init__(self, config: AuditConfig):
        self.config = config
        self.metrics = AuditMetrics()
        self._running = False
        self._event_buffer: deque = deque(maxlen=config.event_buffer_size)
        self._log_file = None

    async def start(self):
        """Start the audit handler."""
        self._running = True
        logger.info("Dataplane Audit starting")

        # Open log file
        await self._open_log_file()

        # Start background tasks
        tasks = [
            asyncio.create_task(self._run_prometheus_server()),
            asyncio.create_task(self._flush_events_loop()),
            asyncio.create_task(self._subscribe_br_events()),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Audit handler error: {e}")
        finally:
            await self._close_log_file()

    def stop(self):
        """Stop the audit handler."""
        self._running = False
        logger.info("Dataplane Audit stopping")

    async def _open_log_file(self):
        """Open the audit log file."""
        try:
            log_path = Path(self.config.audit_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(log_path, "a")
            logger.info(f"Audit log opened: {log_path}")
        except Exception as e:
            logger.error(f"Failed to open audit log: {e}")

    async def _close_log_file(self):
        """Close the audit log file."""
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    async def record_event(self, event: AuditEvent):
        """Record an audit event."""
        # Check severity filter
        severity_order = [s.value for s in AuditSeverity]
        if severity_order.index(event.severity.value) < severity_order.index(self.config.min_severity.value):
            if not self.config.log_all_events:
                return

        # Update metrics
        self.metrics.record_event(event)

        # Add to buffer
        self._event_buffer.append(event)

        # Log high-severity events immediately
        if event.severity in (AuditSeverity.ERROR, AuditSeverity.CRITICAL):
            await self._send_to_judge_luci(event)

        logger.debug(f"Audit event: {event.event_type.value} ({event.severity.value})")

    async def _flush_events_loop(self):
        """Periodically flush events to disk and Judge Luci."""
        while self._running:
            await asyncio.sleep(self.config.flush_interval_seconds)
            await self._flush_events()

    async def _flush_events(self):
        """Flush buffered events."""
        if not self._event_buffer:
            return

        events_to_flush = list(self._event_buffer)
        self._event_buffer.clear()

        # Write to log file
        if self._log_file:
            for event in events_to_flush:
                self._log_file.write(json.dumps(event.to_dict()) + "\n")
            self._log_file.flush()

        # Batch send to Judge Luci
        await self._batch_send_to_judge_luci(events_to_flush)

        logger.debug(f"Flushed {len(events_to_flush)} audit events")

    async def _send_to_judge_luci(self, event: AuditEvent):
        """Send single event to Judge Luci."""
        try:
            # Try Unix socket first
            await self._send_via_socket(event)
        except Exception:
            # Fall back to HTTP
            await self._send_via_http(event)

    async def _batch_send_to_judge_luci(self, events: List[AuditEvent]):
        """Send batch of events to Judge Luci."""
        try:
            # HTTP batch endpoint
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.judge_luci_http}/batch",
                    json={"events": [e.to_dict() for e in events]},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"Judge Luci batch send failed: {resp.status}")
        except Exception as e:
            logger.debug(f"Failed to send to Judge Luci: {e}")

    async def _send_via_socket(self, event: AuditEvent):
        """Send event via Unix socket."""
        # Placeholder - in production would use actual socket
        pass

    async def _send_via_http(self, event: AuditEvent):
        """Send event via HTTP."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.judge_luci_http,
                    json=event.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as resp:
                    pass
        except Exception:
            pass

    async def _subscribe_br_events(self):
        """Subscribe to Border Router events."""
        # In production, this would subscribe to BR event stream
        # For now, we accept events via record_event()
        while self._running:
            await asyncio.sleep(10)

    async def _run_prometheus_server(self):
        """Run Prometheus metrics endpoint."""
        try:
            from aiohttp import web

            async def metrics_handler(request):
                return web.Response(
                    text=self.metrics.to_prometheus(),
                    content_type="text/plain",
                )

            async def health_handler(request):
                return web.Response(text="OK")

            app = web.Application()
            app.router.add_get(self.config.prometheus_path, metrics_handler)
            app.router.add_get("/health", health_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", self.config.prometheus_port)
            await site.start()
            logger.info(f"Audit metrics at :{self.config.prometheus_port}{self.config.prometheus_path}")

            while self._running:
                await asyncio.sleep(1)

        except ImportError:
            logger.warning("aiohttp not available, Prometheus metrics disabled")

    # Event creation helpers
    def create_coherence_violation_event(
        self,
        source_isd_as: str,
        dest_isd_as: str,
        coherence: float,
        threshold: float,
        metadata: dict = None,
    ) -> AuditEvent:
        """Create a coherence violation event."""
        src_isd = int(source_isd_as.split("-")[0])
        dst_isd = int(dest_isd_as.split("-")[0])

        return AuditEvent(
            event_type=AuditEventType.COHERENCE_VIOLATION,
            severity=AuditSeverity.WARNING,
            source_isd_as=source_isd_as,
            destination_isd_as=dest_isd_as,
            source_tier=get_tier_from_isd(src_isd),
            destination_tier=get_tier_from_isd(dst_isd),
            coherence_score=coherence,
            coherence_threshold=threshold,
            metadata=metadata or {},
        )

    def create_pac_consent_event(
        self,
        consent_status: str,
        cbb_did_hash: str,
        sbb_did_hash: str,
        source_isd_as: str = "3-ff00:0:741",
        dest_isd_as: str = "2-ff00:0:528",
        metadata: dict = None,
    ) -> AuditEvent:
        """Create a PAC consent event."""
        if consent_status == "GRANTED":
            event_type = AuditEventType.PAC_CONSENT_GRANTED
            severity = AuditSeverity.INFO
        elif consent_status == "REVOKED":
            event_type = AuditEventType.PAC_CONSENT_REVOKED
            severity = AuditSeverity.WARNING
        else:
            event_type = AuditEventType.PAC_CONSENT_DENIED
            severity = AuditSeverity.WARNING

        return AuditEvent(
            event_type=event_type,
            severity=severity,
            source_isd_as=source_isd_as,
            destination_isd_as=dest_isd_as,
            source_tier="PAC",
            destination_tier=get_tier_from_isd(int(dest_isd_as.split("-")[0])),
            pac_consent_status=consent_status,
            cbb_did_hash=cbb_did_hash,
            sbb_did_hash=sbb_did_hash,
            metadata=metadata or {},
        )

    def create_waypoint_bypass_event(
        self,
        source_isd_as: str,
        dest_isd_as: str,
        expected_waypoint: str,
        metadata: dict = None,
    ) -> AuditEvent:
        """Create a waypoint bypass attempt event."""
        return AuditEvent(
            event_type=AuditEventType.WAYPOINT_BYPASS_ATTEMPT,
            severity=AuditSeverity.ERROR,
            source_isd_as=source_isd_as,
            destination_isd_as=dest_isd_as,
            source_tier=get_tier_from_isd(int(source_isd_as.split("-")[0])),
            destination_tier=get_tier_from_isd(int(dest_isd_as.split("-")[0])),
            waypoint_present=False,
            metadata={**(metadata or {}), "expected_waypoint": expected_waypoint},
        )


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SCION Dataplane Audit for Judge Luci")
    parser.add_argument(
        "--config",
        default="/etc/scion/audit/config.yaml",
        help="Configuration file",
    )
    parser.add_argument(
        "--prometheus-port",
        type=int,
        default=30405,
        help="Prometheus metrics port",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        config = AuditConfig.from_file(str(config_path))
    else:
        config = AuditConfig()

    config.prometheus_port = args.prometheus_port

    # Create and run audit handler
    audit = DataplaneAudit(config)

    try:
        await audit.start()
    except KeyboardInterrupt:
        audit.stop()


if __name__ == "__main__":
    asyncio.run(main())
