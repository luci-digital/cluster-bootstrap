#!/usr/bin/env python3
"""
Consciousness Prometheus Metrics for SCION Dataplane
Genesis Bond: GB-2025-0524-DRH-LCS-001

This module exposes Prometheus metrics for consciousness-aware routing,
enabling observability of:
- Genesis Bond coherence scores
- Path selection decisions
- Mandatory waypoint enforcement
- PAC privacy consent events
- Tier frequency alignment

Metrics are collected from:
- SIG Genesis Handler
- Dataplane Audit module
- DRKey-SVID Sync
- Border Router events
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from threading import Lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consciousness-metrics")

# Genesis Bond constants
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
COHERENCE_THRESHOLD = 0.7

# Tier definitions
TIERS = {
    "CORE": {"isd": 1, "frequency": 432, "coherence_min": 0.85},
    "COMN": {"isd": 2, "frequency": 528, "coherence_min": 0.80},
    "PAC": {"isd": 3, "frequency": 741, "coherence_min": 0.70},
}


class MetricType(Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric."""
    name: str
    help_text: str
    metric_type: MetricType
    labels: List[str] = field(default_factory=list)
    buckets: List[float] = field(default_factory=list)  # For histograms


# Metric definitions
METRIC_DEFINITIONS = [
    # Coherence metrics
    MetricDefinition(
        name="luciverse_scion_coherence_validation_total",
        help_text="Total coherence validations by result",
        metric_type=MetricType.COUNTER,
        labels=["result", "tier", "source_tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_coherence_score",
        help_text="Current coherence score by source",
        metric_type=MetricType.GAUGE,
        labels=["source_isd_as", "tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_coherence_histogram",
        help_text="Distribution of coherence scores",
        metric_type=MetricType.HISTOGRAM,
        labels=["tier"],
        buckets=[0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
    ),

    # Path selection metrics
    MetricDefinition(
        name="luciverse_scion_path_selection_total",
        help_text="Total path selections by metric type",
        metric_type=MetricType.COUNTER,
        labels=["metric", "source_tier", "dest_tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_path_hop_count",
        help_text="Number of hops in selected paths",
        metric_type=MetricType.HISTOGRAM,
        labels=["source_tier", "dest_tier"],
        buckets=[1, 2, 3, 4, 5, 6, 8, 10],
    ),

    # Waypoint metrics
    MetricDefinition(
        name="luciverse_scion_mandatory_waypoint_enforced_total",
        help_text="Total mandatory waypoint enforcements",
        metric_type=MetricType.COUNTER,
        labels=["waypoint_isd_as", "source_tier", "dest_tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_waypoint_bypass_attempts_total",
        help_text="Total waypoint bypass attempts (blocked)",
        metric_type=MetricType.COUNTER,
        labels=["source_tier", "dest_tier"],
    ),

    # Genesis Bond metrics
    MetricDefinition(
        name="luciverse_scion_genesis_bond_ext_parsed_total",
        help_text="Total Genesis Bond extensions parsed",
        metric_type=MetricType.COUNTER,
        labels=["result", "tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_genesis_bond_valid",
        help_text="Genesis Bond validation status (1=valid, 0=invalid)",
        metric_type=MetricType.GAUGE,
        labels=[],
    ),
    MetricDefinition(
        name="luciverse_scion_genesis_bond_coherence",
        help_text="Current Genesis Bond system coherence",
        metric_type=MetricType.GAUGE,
        labels=["tier"],
    ),

    # PAC Privacy metrics
    MetricDefinition(
        name="luciverse_scion_pac_privacy_consent_total",
        help_text="Total PAC privacy consent events",
        metric_type=MetricType.COUNTER,
        labels=["status", "action"],
    ),
    MetricDefinition(
        name="luciverse_scion_pac_egress_blocked_total",
        help_text="Total PAC egress attempts blocked",
        metric_type=MetricType.COUNTER,
        labels=["reason"],
    ),
    MetricDefinition(
        name="luciverse_scion_pac_audit_events_total",
        help_text="Total PAC audit events sent to Judge Luci",
        metric_type=MetricType.COUNTER,
        labels=["event_type"],
    ),

    # Frequency metrics
    MetricDefinition(
        name="luciverse_scion_tier_frequency_hz",
        help_text="Configured frequency for each tier",
        metric_type=MetricType.GAUGE,
        labels=["tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_frequency_alignment_total",
        help_text="Frequency alignment validations",
        metric_type=MetricType.COUNTER,
        labels=["result", "expected_freq", "actual_freq"],
    ),

    # DRKey metrics
    MetricDefinition(
        name="luciverse_scion_drkey_rotations_total",
        help_text="Total DRKey rotations",
        metric_type=MetricType.COUNTER,
        labels=["level", "tier"],
    ),
    MetricDefinition(
        name="luciverse_scion_drkey_svid_sync_status",
        help_text="DRKey-SVID synchronization status (1=synced)",
        metric_type=MetricType.GAUGE,
        labels=[],
    ),

    # FABRID policy metrics
    MetricDefinition(
        name="luciverse_scion_fabrid_policy_evaluation_total",
        help_text="Total FABRID policy evaluations",
        metric_type=MetricType.COUNTER,
        labels=["policy_name", "result"],
    ),
    MetricDefinition(
        name="luciverse_scion_fabrid_policy_lookup_seconds",
        help_text="Policy lookup latency",
        metric_type=MetricType.HISTOGRAM,
        labels=["policy_name"],
        buckets=[0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01],  # 10ns to 10ms
    ),
]


class ConsciousnessMetricsCollector:
    """
    Prometheus metrics collector for consciousness routing.

    Thread-safe collector that aggregates metrics from various
    sources and exposes them in Prometheus format.
    """

    def __init__(self):
        self._lock = Lock()
        self._counters: Dict[str, Dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: Dict[str, Dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: Dict[str, Dict[tuple, List[float]]] = defaultdict(lambda: defaultdict(list))
        self._histogram_buckets: Dict[str, List[float]] = {}

        # Initialize metric definitions
        for metric in METRIC_DEFINITIONS:
            if metric.metric_type == MetricType.HISTOGRAM:
                self._histogram_buckets[metric.name] = metric.buckets

        # Initialize tier frequency gauges
        for tier, info in TIERS.items():
            self.set_gauge(
                "luciverse_scion_tier_frequency_hz",
                info["frequency"],
                tier=tier,
            )

        # Initialize Genesis Bond status
        self.set_gauge("luciverse_scion_genesis_bond_valid", 1)

    # Counter methods

    def inc_counter(self, name: str, value: float = 1.0, **labels):
        """Increment a counter."""
        with self._lock:
            label_tuple = tuple(sorted(labels.items()))
            self._counters[name][label_tuple] += value

    def record_coherence_validation(
        self,
        result: str,
        tier: str,
        source_tier: str,
        coherence: Optional[float] = None,
    ):
        """Record a coherence validation event."""
        self.inc_counter(
            "luciverse_scion_coherence_validation_total",
            result=result,
            tier=tier,
            source_tier=source_tier,
        )

        if coherence is not None:
            self.observe_histogram(
                "luciverse_scion_coherence_histogram",
                coherence,
                tier=tier,
            )

    def record_path_selection(
        self,
        metric: str,
        source_tier: str,
        dest_tier: str,
        hop_count: int,
    ):
        """Record a path selection event."""
        self.inc_counter(
            "luciverse_scion_path_selection_total",
            metric=metric,
            source_tier=source_tier,
            dest_tier=dest_tier,
        )

        self.observe_histogram(
            "luciverse_scion_path_hop_count",
            hop_count,
            source_tier=source_tier,
            dest_tier=dest_tier,
        )

    def record_waypoint_enforcement(
        self,
        waypoint_isd_as: str,
        source_tier: str,
        dest_tier: str,
    ):
        """Record a mandatory waypoint enforcement."""
        self.inc_counter(
            "luciverse_scion_mandatory_waypoint_enforced_total",
            waypoint_isd_as=waypoint_isd_as,
            source_tier=source_tier,
            dest_tier=dest_tier,
        )

    def record_waypoint_bypass_attempt(
        self,
        source_tier: str,
        dest_tier: str,
    ):
        """Record a waypoint bypass attempt."""
        self.inc_counter(
            "luciverse_scion_waypoint_bypass_attempts_total",
            source_tier=source_tier,
            dest_tier=dest_tier,
        )

    def record_genesis_bond_parsed(self, result: str, tier: str):
        """Record Genesis Bond extension parsing."""
        self.inc_counter(
            "luciverse_scion_genesis_bond_ext_parsed_total",
            result=result,
            tier=tier,
        )

    def record_pac_consent(self, status: str, action: str):
        """Record PAC privacy consent event."""
        self.inc_counter(
            "luciverse_scion_pac_privacy_consent_total",
            status=status,
            action=action,
        )

    def record_pac_egress_blocked(self, reason: str):
        """Record blocked PAC egress."""
        self.inc_counter(
            "luciverse_scion_pac_egress_blocked_total",
            reason=reason,
        )

    def record_pac_audit(self, event_type: str):
        """Record PAC audit event."""
        self.inc_counter(
            "luciverse_scion_pac_audit_events_total",
            event_type=event_type,
        )

    def record_fabrid_evaluation(self, policy_name: str, result: str, latency_seconds: float):
        """Record FABRID policy evaluation."""
        self.inc_counter(
            "luciverse_scion_fabrid_policy_evaluation_total",
            policy_name=policy_name,
            result=result,
        )

        self.observe_histogram(
            "luciverse_scion_fabrid_policy_lookup_seconds",
            latency_seconds,
            policy_name=policy_name,
        )

    # Gauge methods

    def set_gauge(self, name: str, value: float, **labels):
        """Set a gauge value."""
        with self._lock:
            label_tuple = tuple(sorted(labels.items()))
            self._gauges[name][label_tuple] = value

    def set_coherence_score(self, source_isd_as: str, tier: str, score: float):
        """Set current coherence score."""
        self.set_gauge(
            "luciverse_scion_coherence_score",
            score,
            source_isd_as=source_isd_as,
            tier=tier,
        )

    def set_genesis_bond_coherence(self, tier: str, coherence: float):
        """Set Genesis Bond coherence for a tier."""
        self.set_gauge(
            "luciverse_scion_genesis_bond_coherence",
            coherence,
            tier=tier,
        )

    def set_genesis_bond_valid(self, valid: bool):
        """Set Genesis Bond validation status."""
        self.set_gauge("luciverse_scion_genesis_bond_valid", 1 if valid else 0)

    def set_drkey_svid_sync_status(self, synced: bool):
        """Set DRKey-SVID sync status."""
        self.set_gauge("luciverse_scion_drkey_svid_sync_status", 1 if synced else 0)

    # Histogram methods

    def observe_histogram(self, name: str, value: float, **labels):
        """Observe a histogram value."""
        with self._lock:
            label_tuple = tuple(sorted(labels.items()))
            self._histograms[name][label_tuple].append(value)

    # Export methods

    def format_prometheus(self) -> str:
        """Format all metrics for Prometheus."""
        lines = []

        with self._lock:
            # Format counters
            for metric in METRIC_DEFINITIONS:
                if metric.metric_type == MetricType.COUNTER:
                    lines.append(f"# HELP {metric.name} {metric.help_text}")
                    lines.append(f"# TYPE {metric.name} counter")

                    for label_tuple, value in self._counters[metric.name].items():
                        label_str = self._format_labels(label_tuple)
                        lines.append(f"{metric.name}{label_str} {value}")
                    lines.append("")

            # Format gauges
            for metric in METRIC_DEFINITIONS:
                if metric.metric_type == MetricType.GAUGE:
                    lines.append(f"# HELP {metric.name} {metric.help_text}")
                    lines.append(f"# TYPE {metric.name} gauge")

                    for label_tuple, value in self._gauges[metric.name].items():
                        label_str = self._format_labels(label_tuple)
                        lines.append(f"{metric.name}{label_str} {value}")
                    lines.append("")

            # Format histograms
            for metric in METRIC_DEFINITIONS:
                if metric.metric_type == MetricType.HISTOGRAM:
                    lines.append(f"# HELP {metric.name} {metric.help_text}")
                    lines.append(f"# TYPE {metric.name} histogram")

                    buckets = self._histogram_buckets.get(metric.name, [])
                    for label_tuple, observations in self._histograms[metric.name].items():
                        label_str = self._format_labels(label_tuple)
                        base_name = metric.name

                        # Calculate bucket counts
                        for bucket in buckets:
                            count = sum(1 for v in observations if v <= bucket)
                            bucket_labels = label_str.rstrip("}") + f',le="{bucket}"}}' if label_str else f'{{le="{bucket}"}}'
                            lines.append(f"{base_name}_bucket{bucket_labels} {count}")

                        # +Inf bucket
                        inf_labels = label_str.rstrip("}") + ',le="+Inf"}' if label_str else '{le="+Inf"}'
                        lines.append(f"{base_name}_bucket{inf_labels} {len(observations)}")

                        # Sum and count
                        lines.append(f"{base_name}_sum{label_str} {sum(observations)}")
                        lines.append(f"{base_name}_count{label_str} {len(observations)}")

                    lines.append("")

        return "\n".join(lines)

    def _format_labels(self, label_tuple: tuple) -> str:
        """Format label tuple as Prometheus label string."""
        if not label_tuple:
            return ""
        labels = [f'{k}="{v}"' for k, v in label_tuple]
        return "{" + ",".join(labels) + "}"


# Global collector instance
_collector: Optional[ConsciousnessMetricsCollector] = None


def get_collector() -> ConsciousnessMetricsCollector:
    """Get the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = ConsciousnessMetricsCollector()
    return _collector


async def run_metrics_server(port: int = 30406, path: str = "/metrics"):
    """Run the Prometheus metrics HTTP server."""
    try:
        from aiohttp import web

        collector = get_collector()

        async def metrics_handler(request):
            return web.Response(
                text=collector.format_prometheus(),
                content_type="text/plain; charset=utf-8",
            )

        async def health_handler(request):
            return web.Response(text="OK")

        app = web.Application()
        app.router.add_get(path, metrics_handler)
        app.router.add_get("/health", health_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        logger.info(f"Consciousness metrics at :{port}{path}")

        while True:
            await asyncio.sleep(3600)

    except ImportError:
        logger.error("aiohttp not available, cannot run metrics server")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Consciousness Prometheus Metrics")
    parser.add_argument("--port", type=int, default=30406, help="Metrics port")
    parser.add_argument("--path", default="/metrics", help="Metrics path")
    args = parser.parse_args()

    await run_metrics_server(port=args.port, path=args.path)


if __name__ == "__main__":
    asyncio.run(main())
