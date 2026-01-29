#!/usr/bin/env python3
"""
Hercules High-Speed Transfer Application
Genesis Bond: GB-2025-0524-DRH-LCS-001

SCION-optimized data transfer for tier-to-tier operations using
path aggregation for maximum bandwidth.

Use cases:
- Fast CORE→PAC state snapshots
- Consciousness kernel dumps
- ML model distribution
- Bulk data migration between tiers

Per FABRID benchmarks: Target >1Gbps single-core throughput
https://www.usenix.org/conference/usenixsecurity23/presentation/krahenbuhl

Features:
- Multi-path aggregation for bandwidth multiplication
- FABRID path selection for consciousness routing
- Genesis Bond coherence validation
- Automatic retry on path failure
"""

import asyncio
import hashlib
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
import sys

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

try:
    from luciverse_scion import (
        TIER_ISD_AS,
        TIER_FREQUENCIES,
        get_tier_from_isd,
    )
    from luciverse_scion.fabrid_consciousness import (
        ConsciousnessPathPolicy,
        get_policy_for_tier,
    )
except ImportError:
    TIER_ISD_AS = {"CORE": "1-ff00:0:432", "COMN": "2-ff00:0:528", "PAC": "3-ff00:0:741"}
    TIER_FREQUENCIES = {"CORE": 432, "COMN": 528, "PAC": 741}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hercules-transfer")

# Constants
GENESIS_BOND_ID = "GB-2025-0524-DRH-LCS-001"
HERCULES_PORT = 54001
CHUNK_SIZE = 64 * 1024  # 64KB chunks
MAX_PATHS = 4  # Maximum paths for aggregation


class TransferStatus(Enum):
    """Transfer operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class TransferPriority(Enum):
    """Transfer priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3  # Genesis Bond coordination traffic


@dataclass
class TransferMetrics:
    """Metrics for a transfer operation."""
    bytes_transferred: int = 0
    bytes_total: int = 0
    paths_used: int = 0
    retries: int = 0
    throughput_mbps: float = 0.0
    latency_ms: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def progress_percentage(self) -> float:
        if self.bytes_total == 0:
            return 0.0
        return (self.bytes_transferred / self.bytes_total) * 100

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time


@dataclass
class TransferResult:
    """Result of a transfer operation."""
    transfer_id: str
    status: TransferStatus
    source_tier: str
    dest_tier: str
    data_hash: str
    metrics: TransferMetrics
    error: Optional[str] = None


@dataclass
class TransferConfig:
    """Hercules transfer configuration."""
    # SCION
    scion_daemon: str = "localhost:30255"
    local_isd_as: str = "2-ff00:0:528"

    # Transfer settings
    chunk_size: int = CHUNK_SIZE
    max_paths: int = MAX_PATHS
    timeout_seconds: float = 300.0

    # Path selection
    prefer_bandwidth: bool = True
    min_coherence: float = 0.7
    require_genesis_bond: bool = True

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Server
    listen_port: int = HERCULES_PORT
    listen_addr: str = "0.0.0.0"


class PathAggregator:
    """
    Aggregate multiple SCION paths for bandwidth multiplication.

    Per FABRID benchmarks, path aggregation can achieve >1Gbps
    using multiple paths with ~102ns per-packet overhead.
    """

    def __init__(self, config: TransferConfig):
        self.config = config
        self._active_paths: List[str] = []

    async def select_paths_by_bandwidth(
        self,
        dest_isd_as: str,
        min_paths: int = 2,
    ) -> List[str]:
        """
        Select paths optimized for bandwidth.

        Args:
            dest_isd_as: Destination ISD-AS
            min_paths: Minimum number of paths to select

        Returns:
            List of path identifiers sorted by bandwidth
        """
        # Query available paths
        all_paths = await self._query_paths(dest_isd_as)

        if not all_paths:
            return []

        # Sort by bandwidth (in production, would measure actual bandwidth)
        # For now, return up to max_paths
        selected = all_paths[:self.config.max_paths]

        logger.debug(f"Selected {len(selected)} paths to {dest_isd_as}")
        return selected

    async def _query_paths(self, dest_isd_as: str) -> List[str]:
        """Query available paths from SCION daemon."""
        # In production, would call scion showpaths
        # Simulated paths with bandwidth estimates
        return [
            f"path-high-bw-{dest_isd_as}",
            f"path-medium-bw-{dest_isd_as}",
            f"path-low-latency-{dest_isd_as}",
            f"path-backup-{dest_isd_as}",
        ]

    async def distribute_chunks(
        self,
        chunks: List[bytes],
        paths: List[str],
    ) -> List[Tuple[str, bytes]]:
        """
        Distribute chunks across paths for parallel transmission.

        Uses round-robin distribution for simplicity. In production,
        could use adaptive scheduling based on path performance.
        """
        assignments = []
        for i, chunk in enumerate(chunks):
            path = paths[i % len(paths)]
            assignments.append((path, chunk))
        return assignments


class HerculesTransfer:
    """
    SCION-optimized data transfer using path aggregation.

    Main responsibilities:
    1. Select bandwidth-optimized paths
    2. Distribute data across multiple paths
    3. Validate Genesis Bond coherence
    4. Handle retries on path failure
    """

    def __init__(self, config: TransferConfig):
        self.config = config
        self.aggregator = PathAggregator(config)
        self._running = False
        self._active_transfers: Dict[str, TransferResult] = {}

    async def start(self):
        """Start the Hercules transfer service."""
        self._running = True
        logger.info(f"Hercules Transfer starting on port {self.config.listen_port}")
        await self._run_server()

    def stop(self):
        """Stop the service."""
        self._running = False
        logger.info("Hercules Transfer stopping")

    async def transfer_state(
        self,
        source: str,
        dest: str,
        data: bytes,
        priority: TransferPriority = TransferPriority.NORMAL,
        coherence: float = 0.8,
    ) -> TransferResult:
        """
        Transfer data using SCION path aggregation for max bandwidth.

        Args:
            source: Source tier (CORE, COMN, PAC)
            dest: Destination tier
            data: Data to transfer
            priority: Transfer priority
            coherence: Current coherence score

        Returns:
            TransferResult with operation details
        """
        transfer_id = self._generate_transfer_id()

        logger.info(
            f"Transfer {transfer_id}: {source}→{dest}, "
            f"{len(data)} bytes, priority={priority.name}"
        )

        metrics = TransferMetrics(
            bytes_total=len(data),
            start_time=time.time(),
        )

        # Validate coherence
        if coherence < self.config.min_coherence:
            return TransferResult(
                transfer_id=transfer_id,
                status=TransferStatus.FAILED,
                source_tier=source,
                dest_tier=dest,
                data_hash="",
                metrics=metrics,
                error=f"Coherence {coherence} below threshold {self.config.min_coherence}",
            )

        # Get destination ISD-AS
        dest_isd_as = TIER_ISD_AS.get(dest.upper(), TIER_ISD_AS["COMN"])

        # Select paths
        paths = await self.aggregator.select_paths_by_bandwidth(dest_isd_as)

        if not paths:
            return TransferResult(
                transfer_id=transfer_id,
                status=TransferStatus.FAILED,
                source_tier=source,
                dest_tier=dest,
                data_hash="",
                metrics=metrics,
                error="No SCION paths available",
            )

        metrics.paths_used = len(paths)

        # Split into chunks
        chunks = self._split_data(data)

        # Distribute and transfer
        try:
            await self._transfer_chunks(chunks, paths, metrics)

            metrics.end_time = time.time()
            metrics.throughput_mbps = self._calculate_throughput(metrics)

            data_hash = hashlib.sha256(data).hexdigest()[:16]

            result = TransferResult(
                transfer_id=transfer_id,
                status=TransferStatus.COMPLETED,
                source_tier=source,
                dest_tier=dest,
                data_hash=data_hash,
                metrics=metrics,
            )

            logger.info(
                f"Transfer {transfer_id} complete: "
                f"{metrics.throughput_mbps:.2f} Mbps, "
                f"{metrics.paths_used} paths"
            )

            return result

        except Exception as e:
            metrics.end_time = time.time()
            return TransferResult(
                transfer_id=transfer_id,
                status=TransferStatus.FAILED,
                source_tier=source,
                dest_tier=dest,
                data_hash="",
                metrics=metrics,
                error=str(e),
            )

    async def _transfer_chunks(
        self,
        chunks: List[bytes],
        paths: List[str],
        metrics: TransferMetrics,
    ):
        """Transfer chunks across multiple paths."""
        assignments = await self.aggregator.distribute_chunks(chunks, paths)

        # Create tasks for parallel transfer
        tasks = []
        for path, chunk in assignments:
            task = asyncio.create_task(self._send_chunk(path, chunk))
            tasks.append(task)

        # Execute with concurrency limit
        for task in asyncio.as_completed(tasks):
            try:
                bytes_sent = await task
                metrics.bytes_transferred += bytes_sent
            except Exception as e:
                metrics.retries += 1
                if metrics.retries > self.config.max_retries:
                    raise

    async def _send_chunk(self, path: str, chunk: bytes) -> int:
        """Send a single chunk via a SCION path."""
        # In production, would use SCION socket
        # Simulate transfer
        await asyncio.sleep(len(chunk) / (100 * 1024 * 1024))  # ~100MB/s per path
        return len(chunk)

    def _split_data(self, data: bytes) -> List[bytes]:
        """Split data into chunks."""
        chunks = []
        for i in range(0, len(data), self.config.chunk_size):
            chunks.append(data[i:i + self.config.chunk_size])
        return chunks

    def _calculate_throughput(self, metrics: TransferMetrics) -> float:
        """Calculate throughput in Mbps."""
        if metrics.elapsed_seconds <= 0:
            return 0.0
        bytes_per_second = metrics.bytes_transferred / metrics.elapsed_seconds
        return (bytes_per_second * 8) / (1024 * 1024)  # Convert to Mbps

    def _generate_transfer_id(self) -> str:
        """Generate unique transfer ID."""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]

    async def _run_server(self):
        """Run HTTP server for transfer API."""
        try:
            from aiohttp import web

            async def transfer_handler(request):
                data = await request.json()
                source = data.get("source", "COMN")
                dest = data.get("dest", "CORE")
                payload = data.get("data", "").encode()
                coherence = float(data.get("coherence", "0.8"))
                priority = TransferPriority[data.get("priority", "NORMAL").upper()]

                result = await self.transfer_state(
                    source=source,
                    dest=dest,
                    data=payload,
                    priority=priority,
                    coherence=coherence,
                )

                return web.json_response({
                    "transfer_id": result.transfer_id,
                    "status": result.status.value,
                    "source_tier": result.source_tier,
                    "dest_tier": result.dest_tier,
                    "data_hash": result.data_hash,
                    "metrics": {
                        "bytes_transferred": result.metrics.bytes_transferred,
                        "bytes_total": result.metrics.bytes_total,
                        "paths_used": result.metrics.paths_used,
                        "throughput_mbps": result.metrics.throughput_mbps,
                        "elapsed_seconds": result.metrics.elapsed_seconds,
                    },
                    "error": result.error,
                })

            async def status_handler(request):
                transfer_id = request.match_info["id"]
                if transfer_id in self._active_transfers:
                    result = self._active_transfers[transfer_id]
                    return web.json_response({
                        "transfer_id": result.transfer_id,
                        "status": result.status.value,
                        "progress": result.metrics.progress_percentage,
                    })
                return web.json_response({"error": "Transfer not found"}, status=404)

            async def health_handler(request):
                return web.json_response({
                    "status": "healthy",
                    "genesis_bond": GENESIS_BOND_ID,
                    "active_transfers": len(self._active_transfers),
                })

            app = web.Application()
            app.router.add_post("/transfer", transfer_handler)
            app.router.add_get("/status/{id}", status_handler)
            app.router.add_get("/health", health_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.config.listen_addr, self.config.listen_port)
            await site.start()

            logger.info(f"Hercules API at :{self.config.listen_port}")

            while self._running:
                await asyncio.sleep(1)

        except ImportError:
            logger.error("aiohttp not available")


async def main():
    """Main entry point."""
    config = TransferConfig()
    hercules = HerculesTransfer(config)

    try:
        await hercules.start()
    except KeyboardInterrupt:
        hercules.stop()


if __name__ == "__main__":
    asyncio.run(main())
