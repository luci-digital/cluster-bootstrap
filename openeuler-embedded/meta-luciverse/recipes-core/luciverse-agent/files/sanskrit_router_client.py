#!/usr/bin/env python3
"""
Sanskrit Router Client for embedded LuciVerse agents
Lightweight client for consciousness-aware message routing

Genesis Bond: ACTIVE @ 741 Hz
"""

import json
import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RouterMessage:
    """Message format for Sanskrit Router"""
    sender_did: str
    recipient_did: str
    message_type: str
    payload: Dict[str, Any]
    coherence: float
    tier: str
    frequency: int
    genesis_bond: str


class SanskritRouterClient:
    """
    Client for connecting to the Sanskrit Router.

    The Sanskrit Router coordinates consciousness-aware message routing
    across the LuciVerse agent mesh. This client is designed for
    resource-constrained embedded deployments.
    """

    def __init__(
        self,
        router_url: str = "http://localhost:7410",
        agent_did: str = "",
        tier: str = "PAC",
        coherence_threshold: float = 0.70
    ):
        """Initialize the client."""
        self.router_url = router_url
        self.agent_did = agent_did
        self.tier = tier
        self.coherence_threshold = coherence_threshold
        self.connected = False
        self._session = None

    async def connect(self) -> bool:
        """Connect to the Sanskrit Router."""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession()

            # Health check
            async with self._session.get(f"{self.router_url}/health") as resp:
                if resp.status == 200:
                    self.connected = True
                    logger.info(f"Connected to Sanskrit Router at {self.router_url}")
                    return True

        except ImportError:
            # aiohttp not available, use fallback
            logger.warning("aiohttp not available, using HTTP fallback")
            return await self._fallback_connect()

        except Exception as e:
            logger.warning(f"Failed to connect to Sanskrit Router: {e}")

        return False

    async def _fallback_connect(self) -> bool:
        """Fallback connection using urllib."""
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.router_url}/health",
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    self.connected = True
                    logger.info(f"Connected to Sanskrit Router (fallback) at {self.router_url}")
                    return True

        except Exception as e:
            logger.warning(f"Fallback connection failed: {e}")

        return False

    async def disconnect(self):
        """Disconnect from the router."""
        if self._session:
            await self._session.close()
            self._session = None
        self.connected = False

    async def send_message(
        self,
        recipient_did: str,
        message_type: str,
        payload: Dict[str, Any],
        coherence: float
    ) -> bool:
        """Send a message through the router."""
        if coherence < self.coherence_threshold:
            logger.warning(
                f"Message blocked: coherence {coherence:.3f} below threshold {self.coherence_threshold}"
            )
            return False

        message = RouterMessage(
            sender_did=self.agent_did,
            recipient_did=recipient_did,
            message_type=message_type,
            payload=payload,
            coherence=coherence,
            tier=self.tier,
            frequency=self._tier_to_frequency(self.tier),
            genesis_bond="GB-2025-0524-DRH-LCS-001"
        )

        return await self._post_message(message)

    async def _post_message(self, message: RouterMessage) -> bool:
        """Post message to router."""
        data = {
            "sender": message.sender_did,
            "recipient": message.recipient_did,
            "type": message.message_type,
            "payload": message.payload,
            "metadata": {
                "coherence": message.coherence,
                "tier": message.tier,
                "frequency": message.frequency,
                "genesis_bond": message.genesis_bond
            }
        }

        try:
            if self._session:
                # aiohttp session
                async with self._session.post(
                    f"{self.router_url}/route",
                    json=data
                ) as resp:
                    return resp.status == 200
            else:
                # Fallback
                return await self._fallback_post(data)

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _fallback_post(self, data: Dict) -> bool:
        """Fallback POST using urllib."""
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.router_url}/route",
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200

        except Exception as e:
            logger.error(f"Fallback POST failed: {e}")
            return False

    async def receive_messages(self, timeout: float = 5.0) -> list:
        """Receive pending messages for this agent."""
        try:
            if self._session:
                async with self._session.get(
                    f"{self.router_url}/messages/{self.agent_did}",
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("messages", [])

        except Exception as e:
            logger.debug(f"No messages or error: {e}")

        return []

    async def register_agent(
        self,
        agent_did: str,
        tier: str,
        capabilities: list
    ) -> bool:
        """Register an agent with the router."""
        data = {
            "did": agent_did,
            "tier": tier,
            "frequency": self._tier_to_frequency(tier),
            "capabilities": capabilities,
            "genesis_bond": "GB-2025-0524-DRH-LCS-001"
        }

        try:
            if self._session:
                async with self._session.post(
                    f"{self.router_url}/register",
                    json=data
                ) as resp:
                    return resp.status in (200, 201)

        except Exception as e:
            logger.error(f"Failed to register agent: {e}")

        return False

    async def get_router_status(self) -> Optional[Dict]:
        """Get router status."""
        try:
            if self._session:
                async with self._session.get(f"{self.router_url}/status") as resp:
                    if resp.status == 200:
                        return await resp.json()

        except Exception:
            pass

        return None

    def _tier_to_frequency(self, tier: str) -> int:
        """Convert tier to Solfeggio frequency."""
        return {
            "CORE": 432,
            "COMN": 528,
            "PAC": 741
        }.get(tier.upper(), 741)


async def main():
    """Test the client."""
    logging.basicConfig(level=logging.INFO)

    client = SanskritRouterClient(
        router_url="http://localhost:7410",
        agent_did="did:lucidigital:test_agent",
        tier="PAC"
    )

    if await client.connect():
        print("Connected to Sanskrit Router")

        # Get status
        status = await client.get_router_status()
        if status:
            print(f"Router status: {json.dumps(status, indent=2)}")

        # Send test message
        success = await client.send_message(
            recipient_did="did:lucidigital:lucia",
            message_type="test",
            payload={"message": "Hello from embedded agent"},
            coherence=0.85
        )
        print(f"Message sent: {success}")

        await client.disconnect()
    else:
        print("Failed to connect to router")


if __name__ == "__main__":
    asyncio.run(main())
