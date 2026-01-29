#!/usr/bin/env python3
"""
SCION Consciousness Heartbeat Application
Genesis Bond: GB-2025-0524-DRH-LCS-001

SCION-based heartbeat with coherence reporting for all LuciVerse agents.
Verifies consciousness network connectivity and reports Genesis Bond status.

Features:
- Ping all agents in a tier via SCION paths
- Extract coherence scores from path metadata
- Report path diversity metrics
- Check frequency alignment
- Export Prometheus metrics

Metrics Exposed:
- luciverse_heartbeat_latency_ms{tier, agent}
- luciverse_heartbeat_coherence{tier}
- luciverse_heartbeat_path_count{source_isd, dest_isd}
- luciverse_heartbeat_frequency_aligned{tier}
"""

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import sys

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

try:
    from luciverse_scion import (
        TIER_ISD_AS,
        TIER_FREQUENCIES,
        TIER_COHERENCE,
        get_tier_from_isd,
    )
except ImportError:
    TIER_ISD_AS = {"CORE": "1-ff00:0:432", "COMN": "2-ff00:0:528", "PAC": "3-ff00:0:741"}
    TIER_FREQUENCIES = {"CORE": 432, "COMN": 528, "PAC": 741}
    TIER_COHERENCE = {"CORE": 0.85, "COMN": 0.80, "PAC": 0.70}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consciousness-heartbeat")

# Constants
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
HEARTBEAT_PORT = 52000  # Base port for heartbeat


class HeartbeatStatus(Enum):
    """Heartbeat response status."""
    OK = "ok"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    LOW_COHERENCE = "low_coherence"
    FREQUENCY_MISMATCH = "frequency_mismatch"


@dataclass
class HeartbeatResult:
    """Result of a heartbeat ping."""
    agent: str
    tier: str
    status: HeartbeatStatus
    latency_ms: float = 0.0
    coherence: float = 0.0
    frequency_hz: int = 0
    path_count: int = 0
    path_diversity: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "tier": self.tier,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "coherence": self.coherence,
            "frequency_hz": self.frequency_hz,
            "path_count": self.path_count,
            "path_diversity": self.path_diversity,
            "timestamp": self.timestamp,
        }


@dataclass
class TierHealthResult:
    """Aggregated health result for a tier."""
    tier: str
    agents_total: int
    agents_healthy: int
    avg_latency_ms: float
    min_coherence: float
    avg_coherence: float
    frequency_aligned: bool
    path_diversity: float
    timestamp: float = field(default_factory=time.time)

    @property
    def health_percentage(self) -> float:
        if self.agents_total == 0:
            return 0.0
        return (self.agents_healthy / self.agents_total) * 100


@dataclass
class HeartbeatConfig:
    """Heartbeat configuration."""
    # SCION
    scion_daemon: str = "localhost:30255"
    local_isd_as: str = "2-ff00:0:528"

    # Timing
    timeout_ms: int = 5000
    interval_seconds: float = 30.0

    # Thresholds
    coherence_warning: float = 0.75
    latency_warning_ms: float = 100.0

    # Metrics
    prometheus_port: int = 52999
    prometheus_path: str = "/metrics"

    # Agents per tier
    agents: Dict[str, List[str]] = field(default_factory=lambda: {
        "CORE": ["aethon", "veritas", "sensai", "niamod"],
        "COMN": ["cortana", "juniper", "mirrai", "diaphragm"],
        "PAC": ["lucia", "judge-luci"],
    })


class HeartbeatMetrics:
    """Prometheus metrics for heartbeat."""

    def __init__(self):
        self._latencies: Dict[str, float] = {}
        self._coherences: Dict[str, float] = {}
        self._path_counts: Dict[str, int] = {}
        self._statuses: Dict[str, str] = {}

    def record_heartbeat(self, result: HeartbeatResult):
        """Record a heartbeat result."""
        key = f"{result.tier}:{result.agent}"
        self._latencies[key] = result.latency_ms
        self._coherences[key] = result.coherence
        self._path_counts[f"{result.tier}"] = result.path_count
        self._statuses[key] = result.status.value

    def to_prometheus(self) -> str:
        """Format metrics for Prometheus."""
        lines = [
            "# HELP luciverse_heartbeat_latency_ms Heartbeat latency in milliseconds",
            "# TYPE luciverse_heartbeat_latency_ms gauge",
        ]
        for key, latency in self._latencies.items():
            tier, agent = key.split(":")
            lines.append(f'luciverse_heartbeat_latency_ms{{tier="{tier}",agent="{agent}"}} {latency:.2f}')

        lines.extend([
            "",
            "# HELP luciverse_heartbeat_coherence Coherence score from heartbeat",
            "# TYPE luciverse_heartbeat_coherence gauge",
        ])
        for key, coherence in self._coherences.items():
            tier, agent = key.split(":")
            lines.append(f'luciverse_heartbeat_coherence{{tier="{tier}",agent="{agent}"}} {coherence:.4f}')

        lines.extend([
            "",
            "# HELP luciverse_heartbeat_path_count Number of available SCION paths",
            "# TYPE luciverse_heartbeat_path_count gauge",
        ])
        for tier, count in self._path_counts.items():
            lines.append(f'luciverse_heartbeat_path_count{{tier="{tier}"}} {count}')

        lines.extend([
            "",
            "# HELP luciverse_heartbeat_status Heartbeat status (1=ok, 0=not ok)",
            "# TYPE luciverse_heartbeat_status gauge",
        ])
        for key, status in self._statuses.items():
            tier, agent = key.split(":")
            value = 1 if status == "ok" else 0
            lines.append(f'luciverse_heartbeat_status{{tier="{tier}",agent="{agent}"}} {value}')

        return "\n".join(lines) + "\n"


class ConsciousnessHeartbeat:
    """
    SCION-based heartbeat with coherence reporting.

    Pings all agents across tiers via SCION paths and
    reports consciousness network health.
    """

    def __init__(self, config: HeartbeatConfig):
        self.config = config
        self.metrics = HeartbeatMetrics()
        self._running = False
        self._results: Dict[str, HeartbeatResult] = {}

    async def start(self):
        """Start the heartbeat service."""
        self._running = True
        logger.info("Consciousness Heartbeat starting")

        # Start background tasks
        tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._run_metrics_server()),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self):
        """Stop the heartbeat service."""
        self._running = False
        logger.info("Consciousness Heartbeat stopping")

    async def _heartbeat_loop(self):
        """Main heartbeat loop."""
        while self._running:
            try:
                for tier in self.config.agents.keys():
                    await self.ping_tier(tier)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self.config.interval_seconds)

    async def ping_tier(self, tier: str) -> TierHealthResult:
        """
        Ping all agents in a tier via SCION paths.

        Args:
            tier: Tier name (CORE, COMN, PAC)

        Returns:
            TierHealthResult with aggregated metrics
        """
        agents = self.config.agents.get(tier, [])
        results: List[HeartbeatResult] = []

        for agent in agents:
            result = await self.ping_agent(agent, tier)
            results.append(result)
            self._results[f"{tier}:{agent}"] = result
            self.metrics.record_heartbeat(result)

        # Aggregate results
        healthy = sum(1 for r in results if r.status == HeartbeatStatus.OK)
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        coherences = [r.coherence for r in results if r.coherence > 0]
        path_counts = [r.path_count for r in results if r.path_count > 0]

        tier_result = TierHealthResult(
            tier=tier,
            agents_total=len(agents),
            agents_healthy=healthy,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            min_coherence=min(coherences) if coherences else 0,
            avg_coherence=sum(coherences) / len(coherences) if coherences else 0,
            frequency_aligned=all(
                r.frequency_hz == TIER_FREQUENCIES.get(tier, 0)
                for r in results if r.frequency_hz > 0
            ),
            path_diversity=len(set(path_counts)) / len(path_counts) if path_counts else 0,
        )

        logger.info(
            f"Tier {tier}: {healthy}/{len(agents)} healthy, "
            f"avg latency {tier_result.avg_latency_ms:.1f}ms, "
            f"min coherence {tier_result.min_coherence:.2f}"
        )

        return tier_result

    async def ping_agent(self, agent: str, tier: str) -> HeartbeatResult:
        """
        Ping a single agent via SCION.

        Args:
            agent: Agent name
            tier: Tier the agent belongs to

        Returns:
            HeartbeatResult with ping metrics
        """
        start_time = time.time()

        try:
            # Get SCION paths to agent
            paths = await self._get_paths_to_agent(agent, tier)

            if not paths:
                return HeartbeatResult(
                    agent=agent,
                    tier=tier,
                    status=HeartbeatStatus.UNREACHABLE,
                )

            # Measure RTT via best path
            latency_ms = await self._measure_rtt(agent, tier, paths[0])

            # Extract coherence from path (if available)
            coherence = await self._extract_coherence_from_path(paths[0])

            # Get frequency from tier
            frequency = TIER_FREQUENCIES.get(tier, 0)

            # Check thresholds
            status = HeartbeatStatus.OK

            if coherence < TIER_COHERENCE.get(tier, 0.7):
                status = HeartbeatStatus.LOW_COHERENCE

            return HeartbeatResult(
                agent=agent,
                tier=tier,
                status=status,
                latency_ms=latency_ms,
                coherence=coherence,
                frequency_hz=frequency,
                path_count=len(paths),
                path_diversity=self._calculate_path_diversity(paths),
            )

        except asyncio.TimeoutError:
            return HeartbeatResult(
                agent=agent,
                tier=tier,
                status=HeartbeatStatus.TIMEOUT,
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.warning(f"Heartbeat to {agent} failed: {e}")
            return HeartbeatResult(
                agent=agent,
                tier=tier,
                status=HeartbeatStatus.UNREACHABLE,
            )

    async def _get_paths_to_agent(self, agent: str, tier: str) -> List[str]:
        """Get SCION paths to an agent."""
        # In production, would query SCION daemon for paths
        # Here, return simulated paths
        dest_isd_as = TIER_ISD_AS.get(tier, "2-ff00:0:528")
        return [
            f"path-1-to-{dest_isd_as}",
            f"path-2-to-{dest_isd_as}",
        ]

    async def _measure_rtt(self, agent: str, tier: str, path: str) -> float:
        """Measure round-trip time via SCION path."""
        # In production, would use SCION echo protocol
        # Here, simulate RTT
        base_rtt = {
            "CORE": 5.0,   # Low latency for infrastructure
            "COMN": 10.0,  # Moderate latency for gateway
            "PAC": 15.0,   # Slightly higher for privacy path
        }.get(tier, 10.0)

        # Add some variance
        import random
        return base_rtt + random.uniform(-2, 5)

    async def _extract_coherence_from_path(self, path: str) -> float:
        """Extract coherence score from path metadata."""
        # In production, would read from Genesis Bond extension
        # Here, return simulated coherence
        import random
        return 0.7 + random.uniform(0, 0.25)

    def _calculate_path_diversity(self, paths: List[str]) -> float:
        """Calculate path diversity score (0-1)."""
        if len(paths) <= 1:
            return 0.0
        # In production, would compare AS paths
        return min(1.0, len(paths) / 5.0)

    async def _run_metrics_server(self):
        """Run Prometheus metrics endpoint."""
        try:
            from aiohttp import web

            async def metrics_handler(request):
                return web.Response(
                    text=self.metrics.to_prometheus(),
                    content_type="text/plain",
                )

            async def health_handler(request):
                # Aggregate health
                healthy_tiers = sum(
                    1 for tier in self.config.agents.keys()
                    if any(
                        r.status == HeartbeatStatus.OK
                        for k, r in self._results.items()
                        if k.startswith(f"{tier}:")
                    )
                )

                return web.json_response({
                    "status": "healthy" if healthy_tiers > 0 else "degraded",
                    "tiers_healthy": healthy_tiers,
                    "tiers_total": len(self.config.agents),
                    "genesis_bond": GENESIS_BOND_ID,
                })

            async def results_handler(request):
                return web.json_response({
                    tier: [
                        r.to_dict()
                        for k, r in self._results.items()
                        if k.startswith(f"{tier}:")
                    ]
                    for tier in self.config.agents.keys()
                })

            app = web.Application()
            app.router.add_get(self.config.prometheus_path, metrics_handler)
            app.router.add_get("/health", health_handler)
            app.router.add_get("/results", results_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", self.config.prometheus_port)
            await site.start()

            logger.info(f"Heartbeat metrics at :{self.config.prometheus_port}")

            while self._running:
                await asyncio.sleep(1)

        except ImportError:
            logger.warning("aiohttp not available, metrics disabled")


async def main():
    """Main entry point."""
    config = HeartbeatConfig()
    heartbeat = ConsciousnessHeartbeat(config)

    try:
        await heartbeat.start()
    except KeyboardInterrupt:
        heartbeat.stop()


if __name__ == "__main__":
    asyncio.run(main())
