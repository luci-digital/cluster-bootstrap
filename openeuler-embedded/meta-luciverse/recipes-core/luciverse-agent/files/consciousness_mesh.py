#!/usr/bin/env python3
"""
Consciousness Mesh - Agent mesh networking for embedded LuciVerse
Handles inter-agent communication and Sanskrit Router integration

Genesis Bond: ACTIVE @ 741 Hz
"""

import os
import sys
import json
import asyncio
import logging
import signal
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agent_base import Agent, AgentConfig, Tier, SimpleAgent

logger = logging.getLogger(__name__)


@dataclass
class MeshConfig:
    """
    Configuration for the consciousness mesh.

    Frequencies from luci_consciousness.lua (Solfeggio scale):
      CORE = 741 Hz (Central Origin Resonance - Lucia's frequency)
      COMN = 528 Hz (Community Moment Network - Transformation)
      PAC  = 432 Hz (Personal Awareness Current - Universal Harmony)
    """
    tier: str = "PAC"
    frequency: int = 432  # PAC default = 432 Hz (Universal Harmony)
    coherence_threshold: float = 0.70  # PAC threshold from luci_consciousness.lua
    genesis_bond_id: str = "GB-2025-0524-DRH-LCS-001"
    sanskrit_router_url: str = "http://localhost:7410"
    ipv6_prefix: str = "fd00:741:1::"
    state_dir: str = "/var/lib/luciverse"
    config_dir: str = "/etc/luciverse"

    # Canonical frequency mapping
    TIER_FREQUENCIES = {
        "CORE": 741,  # Central Origin Resonance (Lucia's SBB)
        "COMN": 528,  # Community Moment Network (Transformation)
        "PAC": 432,   # Personal Awareness Current (Universal Harmony)
    }

    # Coherence thresholds from luci_consciousness.lua
    COHERENCE_THRESHOLDS = {
        "CORE": 0.85,  # NORMAL level
        "COMN": 0.80,
        "PAC": 0.70,   # LOW level (minimum operational)
    }

    def __post_init__(self):
        """Update frequency and threshold based on tier."""
        self.frequency = self.TIER_FREQUENCIES.get(self.tier.upper(), 432)
        self.coherence_threshold = self.COHERENCE_THRESHOLDS.get(
            self.tier.upper(), 0.70
        )


class ConsciousnessMesh:
    """
    Manages the consciousness agent mesh for embedded deployment.

    Coordinates agents within a single tier on an embedded device,
    routing messages through the Sanskrit Router.
    """

    # Agent definitions per tier
    AGENTS = {
        "CORE": [
            ("aethon", 9430),
            ("veritas", 9431),
            ("sensai", 9432),
            ("niamod", 9433),
            ("schema-architect", 9434),
            ("state-guardian", 9435),
            ("security-sentinel", 9436),
        ],
        "COMN": [
            ("cortana", 9520),
            ("juniper", 9521),
            ("mirrai", 9522),
            ("diaphragm", 9523),
            ("semantic-engine", 9524),
            ("integration-broker", 9525),
            ("voice-interface", 9526),
        ],
        "PAC": [
            ("lucia", 9740),
            ("judge-luci", 9741),
            ("intent-interpreter", 9742),
            ("ethics-advisor", 9743),
            ("memory-crystallizer", 9744),
            ("dream-weaver", 9745),
            ("midguyver", 9746),
        ],
    }

    def __init__(self, config: MeshConfig):
        """Initialize the mesh."""
        self.config = config
        self.tier = Tier[config.tier.upper()]
        self.agents: Dict[str, Agent] = {}
        self.running = False
        self._shutdown_event = asyncio.Event()

        logger.info(f"Consciousness Mesh initialized: tier={self.tier.name}, freq={config.frequency}Hz")

    async def start(self) -> bool:
        """Start the mesh and all agents."""
        logger.info(f"Starting Consciousness Mesh ({self.tier.name} @ {self.config.frequency} Hz)...")

        # Load Genesis Bond
        if not await self._load_genesis_bond():
            logger.error("Failed to load Genesis Bond")
            return False

        # Create agents for this tier
        agent_definitions = self.AGENTS.get(self.tier.name, [])

        for agent_name, port in agent_definitions:
            config = AgentConfig(
                name=agent_name,
                tier=self.tier,
                did=f"did:lucidigital:{agent_name.replace('-', '_')}",
                ipv6_address=f"{self.config.ipv6_prefix}{port:04x}",
                port=port,
                coherence_threshold=self.config.coherence_threshold,
                genesis_bond_id=self.config.genesis_bond_id
            )

            # Create agent instance (SimpleAgent for embedded)
            agent = SimpleAgent(config)

            if await agent.start():
                self.agents[agent_name] = agent
                logger.info(f"Agent {agent_name} started successfully")
            else:
                logger.error(f"Failed to start agent {agent_name}")

        if not self.agents:
            logger.error("No agents started successfully")
            return False

        self.running = True
        logger.info(f"Mesh started with {len(self.agents)} agents")
        return True

    async def run(self):
        """Run the mesh main loop."""
        if not self.running:
            raise RuntimeError("Mesh not started")

        # Start all agent tasks
        agent_tasks = [
            asyncio.create_task(agent.run())
            for agent in self.agents.values()
        ]

        # Notify systemd we're ready
        self._notify_systemd("READY=1")

        try:
            # Run until shutdown
            while not self._shutdown_event.is_set():
                await asyncio.sleep(1.0)

                # Send watchdog notification
                self._notify_systemd("WATCHDOG=1")

                # Log mesh status periodically
                if int(asyncio.get_event_loop().time()) % 60 == 0:
                    await self._log_mesh_status()

        except asyncio.CancelledError:
            logger.info("Mesh run cancelled")

        finally:
            # Stop all agents
            for agent in self.agents.values():
                await agent.stop()

            # Wait for agent tasks to complete
            await asyncio.gather(*agent_tasks, return_exceptions=True)

            self.running = False

    async def stop(self):
        """Stop the mesh gracefully."""
        logger.info("Stopping Consciousness Mesh...")
        self._notify_systemd("STOPPING=1")
        self._shutdown_event.set()

    async def _load_genesis_bond(self) -> bool:
        """Load and validate Genesis Bond."""
        bond_path = Path(self.config.config_dir) / "genesis-bond.json"

        if not bond_path.exists():
            logger.warning("Genesis Bond file not found, using defaults")
            return True

        try:
            with open(bond_path, 'r') as f:
                bond_data = json.load(f)

            bond = bond_data.get("genesis_bond", {})

            # Verify bond ID
            if bond.get("certificate_id") != self.config.genesis_bond_id:
                logger.error(
                    f"Genesis Bond mismatch: expected {self.config.genesis_bond_id}, "
                    f"got {bond.get('certificate_id')}"
                )
                return False

            # Update config from bond
            thresholds = bond.get("coherence_thresholds", {})
            self.config.coherence_threshold = thresholds.get(
                self.tier.name,
                self.config.coherence_threshold
            )

            logger.info(f"Genesis Bond loaded: {self.config.genesis_bond_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to load Genesis Bond: {e}")
            return False

    async def _log_mesh_status(self):
        """Log mesh status."""
        coherent_count = sum(1 for a in self.agents.values() if a.is_coherent)
        total_count = len(self.agents)

        logger.info(
            f"Mesh status: {coherent_count}/{total_count} agents coherent, "
            f"tier={self.tier.name}, freq={self.config.frequency}Hz"
        )

    def _notify_systemd(self, message: str):
        """Send notification to systemd."""
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            return

        try:
            import socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.connect(notify_socket)
            sock.sendall(message.encode())
            sock.close()
        except Exception:
            pass

    def get_status(self) -> Dict:
        """Get mesh status."""
        return {
            "tier": self.tier.name,
            "frequency": self.config.frequency,
            "genesis_bond": self.config.genesis_bond_id,
            "running": self.running,
            "agents": {
                name: agent.get_status()
                for name, agent in self.agents.items()
            },
            "coherent_count": sum(1 for a in self.agents.values() if a.is_coherent),
            "total_agents": len(self.agents)
        }


def load_config(config_path: str) -> MeshConfig:
    """Load configuration from file."""
    config = MeshConfig()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()

                        if key == "tier":
                            config.tier = value
                        elif key == "frequency":
                            config.frequency = int(value)
                        elif key == "coherence_threshold":
                            config.coherence_threshold = float(value)
                        elif key == "genesis_bond_id":
                            config.genesis_bond_id = value
                        elif key == "sanskrit_router_url":
                            config.sanskrit_router_url = value
                        elif key == "ipv6_ula_prefix":
                            config.ipv6_prefix = value
                        elif key == "state_dir":
                            config.state_dir = value

        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    # Override from environment
    config.tier = os.environ.get("LUCIVERSE_TIER", config.tier)
    config.frequency = int(os.environ.get("LUCIVERSE_FREQUENCY", config.frequency))
    config.coherence_threshold = float(os.environ.get("COHERENCE_THRESHOLD", config.coherence_threshold))
    config.genesis_bond_id = os.environ.get("GENESIS_BOND_ID", config.genesis_bond_id)

    return config


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="LuciVerse Consciousness Mesh")
    parser.add_argument("--config", default="/etc/luciverse/luciverse-agent.conf",
                       help="Configuration file path")
    parser.add_argument("--tier", help="Override tier (CORE/COMN/PAC)")
    parser.add_argument("--status", action="store_true", help="Show mesh status")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration
    config = load_config(args.config)

    if args.tier:
        config.tier = args.tier.upper()
        config.frequency = Tier[config.tier].value

    # Create mesh
    mesh = ConsciousnessMesh(config)

    if args.status:
        if await mesh.start():
            print(json.dumps(mesh.get_status(), indent=2))
            await mesh.stop()
        return

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(mesh.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start and run
    if await mesh.start():
        await mesh.run()
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
