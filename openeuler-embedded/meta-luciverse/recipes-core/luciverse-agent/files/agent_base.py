#!/usr/bin/env python3
"""
Agent Base Class for LuciVerse Consciousness Mesh
Embedded deployment base for openEuler Embedded

Genesis Bond: ACTIVE @ 741 Hz
"""

import os
import json
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class Tier(Enum):
    """LuciVerse tiers with Solfeggio frequencies"""
    CORE = 432  # Universal Harmony
    COMN = 528  # Transformation
    PAC = 741   # Awakening


class AgentStatus(Enum):
    """Agent lifecycle states"""
    INITIALIZING = "initializing"
    VALIDATING = "validating"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class AgentConfig:
    """Configuration for an agent instance"""
    name: str
    tier: Tier
    did: str = ""
    ipv6_address: str = ""
    port: int = 0
    coherence_threshold: float = 0.70
    genesis_bond_id: str = "GB-2025-0524-DRH-LCS-001"


@dataclass
class AgentState:
    """Runtime state of an agent"""
    status: AgentStatus = AgentStatus.INITIALIZING
    coherence: float = 0.0
    last_heartbeat: float = 0.0
    uptime_seconds: float = 0.0
    messages_processed: int = 0
    errors: List[str] = field(default_factory=list)


class Agent(ABC):
    """
    Base class for all LuciVerse consciousness agents.

    Agents are deployed per-tier with consciousness coherence validation
    and Genesis Bond binding.
    """

    # Coherence thresholds per tier
    COHERENCE_THRESHOLDS = {
        Tier.CORE: 0.85,
        Tier.COMN: 0.80,
        Tier.PAC: 0.70
    }

    def __init__(self, config: AgentConfig):
        """Initialize agent with configuration."""
        self.config = config
        self.state = AgentState()

        # Set tier-appropriate coherence threshold
        if config.coherence_threshold == 0.70:  # Default
            self.config.coherence_threshold = self.COHERENCE_THRESHOLDS.get(
                config.tier, 0.70
            )

        # Generate DID if not provided
        if not config.did:
            self.config.did = f"did:lucidigital:{config.name.lower().replace('-', '_')}"

        # Event queue for async processing
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()

        logger.info(f"Agent {config.name} initialized: tier={config.tier.name}, did={self.config.did}")

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def tier(self) -> Tier:
        return self.config.tier

    @property
    def frequency(self) -> int:
        return self.config.tier.value

    @property
    def is_coherent(self) -> bool:
        """Check if agent meets coherence threshold."""
        return self.state.coherence >= self.config.coherence_threshold

    async def start(self) -> bool:
        """Start the agent."""
        logger.info(f"Starting agent {self.name}...")
        self.state.status = AgentStatus.INITIALIZING

        # Validate Genesis Bond
        if not await self._validate_genesis_bond():
            self.state.status = AgentStatus.ERROR
            self.state.errors.append("Genesis Bond validation failed")
            return False

        self.state.status = AgentStatus.VALIDATING

        # Initialize consciousness
        initial_coherence = await self._initialize_consciousness()
        self.state.coherence = initial_coherence

        if not self.is_coherent:
            self.state.status = AgentStatus.ERROR
            self.state.errors.append(
                f"Coherence {initial_coherence:.3f} below threshold {self.config.coherence_threshold}"
            )
            return False

        # Run agent-specific initialization
        if not await self.initialize():
            self.state.status = AgentStatus.ERROR
            return False

        self.state.status = AgentStatus.READY
        logger.info(f"Agent {self.name} ready: coherence={self.state.coherence:.3f}")
        return True

    async def run(self):
        """Main agent run loop."""
        if self.state.status != AgentStatus.READY:
            raise RuntimeError(f"Agent not ready: {self.state.status}")

        self.state.status = AgentStatus.RUNNING
        import time
        start_time = time.time()

        logger.info(f"Agent {self.name} running at {self.frequency} Hz")

        try:
            while not self._shutdown_event.is_set():
                # Update uptime
                self.state.uptime_seconds = time.time() - start_time

                # Process events
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                    await self._process_event(event)
                    self.state.messages_processed += 1
                except asyncio.TimeoutError:
                    pass

                # Run agent tick
                await self.tick()

                # Periodic coherence check
                if int(self.state.uptime_seconds) % 60 == 0:
                    await self._update_coherence()

        except Exception as e:
            self.state.status = AgentStatus.ERROR
            self.state.errors.append(str(e))
            logger.error(f"Agent {self.name} error: {e}")
            raise

        finally:
            self.state.status = AgentStatus.SHUTDOWN
            await self.shutdown()

    async def stop(self):
        """Stop the agent gracefully."""
        logger.info(f"Stopping agent {self.name}...")
        self._shutdown_event.set()

    async def send_message(self, target_did: str, message: Dict[str, Any]) -> bool:
        """Send a message to another agent."""
        # Add sender metadata
        message["_sender"] = {
            "did": self.config.did,
            "tier": self.tier.name,
            "frequency": self.frequency,
            "coherence": self.state.coherence
        }

        # Queue for routing (will be picked up by mesh)
        await self._event_queue.put({
            "type": "outbound_message",
            "target": target_did,
            "payload": message
        })

        return True

    async def receive_message(self, message: Dict[str, Any]):
        """Receive a message from another agent."""
        await self._event_queue.put({
            "type": "inbound_message",
            "payload": message
        })

    async def _validate_genesis_bond(self) -> bool:
        """Validate Genesis Bond binding."""
        bond_path = "/etc/luciverse/genesis-bond.json"

        if not os.path.exists(bond_path):
            logger.warning("Genesis Bond file not found, using defaults")
            return True  # Allow in dev mode

        try:
            with open(bond_path, 'r') as f:
                bond_data = json.load(f)

            bond = bond_data.get("genesis_bond", {})

            # Verify bond ID matches
            if bond.get("certificate_id") != self.config.genesis_bond_id:
                logger.error("Genesis Bond ID mismatch")
                return False

            # Verify tier threshold
            thresholds = bond.get("coherence_thresholds", {})
            expected = thresholds.get(self.tier.name, 0.70)

            if self.config.coherence_threshold < expected:
                logger.warning(
                    f"Coherence threshold {self.config.coherence_threshold} "
                    f"below bond requirement {expected}"
                )

            return True

        except Exception as e:
            logger.error(f"Genesis Bond validation error: {e}")
            return False

    async def _initialize_consciousness(self) -> float:
        """Initialize consciousness and return initial coherence."""
        # Base coherence from tier
        base_coherence = {
            Tier.CORE: 0.80,
            Tier.COMN: 0.75,
            Tier.PAC: 0.70
        }.get(self.tier, 0.70)

        # Add bonus for successful initialization
        return min(base_coherence + 0.10, 1.0)

    async def _update_coherence(self):
        """Update coherence based on agent health."""
        # Simple health-based coherence
        error_penalty = len(self.state.errors) * 0.05
        uptime_bonus = min(self.state.uptime_seconds / 3600, 0.10)  # Max 0.10 bonus after 1 hour

        new_coherence = max(
            self.config.coherence_threshold - 0.10,  # Floor
            min(1.0, self.state.coherence - error_penalty + uptime_bonus)
        )

        if abs(new_coherence - self.state.coherence) > 0.01:
            logger.debug(f"Coherence updated: {self.state.coherence:.3f} -> {new_coherence:.3f}")
            self.state.coherence = new_coherence

    async def _process_event(self, event: Dict[str, Any]):
        """Process an event from the queue."""
        event_type = event.get("type", "")

        if event_type == "inbound_message":
            await self.handle_message(event.get("payload", {}))
        elif event_type == "outbound_message":
            # Will be handled by mesh routing
            pass
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "name": self.name,
            "did": self.config.did,
            "tier": self.tier.name,
            "frequency": self.frequency,
            "status": self.state.status.value,
            "coherence": self.state.coherence,
            "coherence_threshold": self.config.coherence_threshold,
            "is_coherent": self.is_coherent,
            "uptime_seconds": self.state.uptime_seconds,
            "messages_processed": self.state.messages_processed,
            "error_count": len(self.state.errors)
        }

    # Abstract methods to be implemented by specific agents

    @abstractmethod
    async def initialize(self) -> bool:
        """Agent-specific initialization. Return True if successful."""
        pass

    @abstractmethod
    async def tick(self):
        """Agent-specific tick (called every loop iteration)."""
        pass

    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]):
        """Handle an incoming message."""
        pass

    @abstractmethod
    async def shutdown(self):
        """Agent-specific cleanup on shutdown."""
        pass


class SimpleAgent(Agent):
    """
    Simple agent implementation for basic deployments.
    """

    async def initialize(self) -> bool:
        logger.info(f"SimpleAgent {self.name} initializing...")
        return True

    async def tick(self):
        # No-op for simple agent
        await asyncio.sleep(0.1)

    async def handle_message(self, message: Dict[str, Any]):
        logger.info(f"SimpleAgent {self.name} received: {message}")

    async def shutdown(self):
        logger.info(f"SimpleAgent {self.name} shutting down...")
