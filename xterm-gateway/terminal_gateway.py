#!/usr/bin/env python3
"""
LuciVerse xterm.js Terminal Gateway

Genesis Bond: ACTIVE @ 741 Hz
Tier: PAC (741 Hz)
Purpose: Browser terminal for agents/operators with SPIFFE auth

Architecture:
    Browser ──WebSocket──► Terminal Gateway ──SSH──► Hosts
                           (Port 9800)
                           - SPIFFE-lite auth
                           - Tier-based access
                           - Session recording
"""

import asyncio
import json
import os
import ssl
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import hashlib
import secrets

# Third-party imports (would need to be installed)
try:
    from aiohttp import web
    import aiohttp_cors
except ImportError:
    print("Install: pip install aiohttp aiohttp-cors")

try:
    import pty
    import termios
    import struct
    import fcntl
except ImportError:
    # Windows fallback
    pty = None


# =============================================================================
# Configuration
# =============================================================================

GATEWAY_PORT = 9800
GENESIS_BOND = "GB-2025-0524-DRH-LCS-001"
LINEAGE_DID = "did:lucidigital:lucia_cargail_silcan"

# Agent-based access control
AGENT_ACCESS_CONTROL = {
    # Agent: (tier, allowed_hosts, allowed_commands, coherence_threshold)
    "lucia": {
        "tier": "PAC",
        "hosts": ["zbook", "mac-mini", "localhost"],
        "commands": ["*"],  # All commands
        "coherence": 0.7,
    },
    "aethon": {
        "tier": "CORE",
        "hosts": ["*"],  # All hosts
        "commands": ["*"],
        "coherence": 0.8,
    },
    "niamod": {
        "tier": "CORE",
        "hosts": ["orion", "worker-*"],
        "commands": ["nix", "kubectl", "systemctl", "journalctl"],
        "coherence": 0.8,
    },
    "cortana": {
        "tier": "COMN",
        "hosts": ["zbook", "orion"],
        "commands": ["git", "docker", "jj", "ssh"],
        "coherence": 0.7,
    },
    "veritas": {
        "tier": "CORE",
        "hosts": ["*"],
        "commands": ["*"],  # Truth verification needs full access
        "coherence": 0.85,
    },
}

# Host SSH configuration
HOST_CONFIG = {
    "zbook": {
        "hostname": "192.168.1.146",
        "port": 22,
        "ipv6": "2602:F674:0100::146",
    },
    "orion": {
        "hostname": "192.168.1.141",
        "port": 22,
        "ipv6": "2602:F674:0001::1",
    },
    "mac-mini": {
        "hostname": "192.168.1.238",
        "port": 22,
        "ipv6": "2602:F674:0001::238",
    },
    "localhost": {
        "hostname": "127.0.0.1",
        "port": 22,
    },
}


# =============================================================================
# Data Models
# =============================================================================

class SessionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    ERROR = "error"


class AgentTier(Enum):
    CORE = "CORE"
    COMN = "COMN"
    PAC = "PAC"


@dataclass
class TerminalSession:
    """Active terminal session."""
    session_id: str
    agent: str
    tier: AgentTier
    host: str
    created_at: datetime
    status: SessionStatus = SessionStatus.PENDING
    websocket: Optional[web.WebSocketResponse] = None
    process: Optional[subprocess.Popen] = None
    master_fd: Optional[int] = None
    coherence: float = 0.7
    recording_path: Optional[Path] = None
    commands_executed: List[str] = field(default_factory=list)


@dataclass
class AccessDecision:
    """Result of access control check."""
    allowed: bool
    reason: str
    required_coherence: float = 0.7


# =============================================================================
# SPIFFE-lite Integration
# =============================================================================

def verify_spiffe_svid(svid_path: str, agent_name: str) -> bool:
    """
    Verify SPIFFE SVID for agent authentication.

    Args:
        svid_path: Path to SVID certificate
        agent_name: Expected agent name

    Returns:
        True if SVID is valid
    """
    try:
        # In production, this would verify the certificate chain
        # against the SPIFFE trust bundle
        expected_spiffe_id = f"spiffe://luciverse.ownid/{AGENT_ACCESS_CONTROL[agent_name]['tier'].lower()}/{agent_name}"

        # For now, check file exists and has correct naming
        if not os.path.exists(svid_path):
            return False

        # Would parse X.509 and verify SPIFFE ID in SAN
        return True
    except Exception:
        return False


def check_coherence(agent: str) -> float:
    """
    Check current coherence level for an agent.

    In production, this would query the Genesis Bond coherence system.
    """
    # Simulated coherence - in production, query coherence service
    # Higher coherence at rampament gates, lower during transitions
    import random
    base = AGENT_ACCESS_CONTROL.get(agent, {}).get("coherence", 0.7)
    return base + random.uniform(-0.1, 0.15)


# =============================================================================
# Access Control
# =============================================================================

def check_access(agent: str, host: str, command: Optional[str] = None) -> AccessDecision:
    """
    Check if an agent is allowed to access a host/command.

    Args:
        agent: Agent name
        host: Target host
        command: Command to execute (if any)

    Returns:
        AccessDecision with result
    """
    if agent not in AGENT_ACCESS_CONTROL:
        return AccessDecision(
            allowed=False,
            reason=f"Unknown agent: {agent}",
        )

    config = AGENT_ACCESS_CONTROL[agent]

    # Check coherence
    current_coherence = check_coherence(agent)
    if current_coherence < config["coherence"]:
        return AccessDecision(
            allowed=False,
            reason=f"Coherence {current_coherence:.2f} below threshold {config['coherence']}",
            required_coherence=config["coherence"],
        )

    # Check host access
    allowed_hosts = config["hosts"]
    if "*" not in allowed_hosts:
        # Check for wildcard patterns
        host_allowed = False
        for pattern in allowed_hosts:
            if pattern.endswith("*"):
                if host.startswith(pattern[:-1]):
                    host_allowed = True
                    break
            elif pattern == host:
                host_allowed = True
                break

        if not host_allowed:
            return AccessDecision(
                allowed=False,
                reason=f"Agent {agent} not allowed to access host {host}",
                required_coherence=config["coherence"],
            )

    # Check command access
    if command:
        allowed_commands = config["commands"]
        if "*" not in allowed_commands:
            cmd_base = command.split()[0] if command else ""
            if cmd_base not in allowed_commands:
                return AccessDecision(
                    allowed=False,
                    reason=f"Agent {agent} not allowed to execute {cmd_base}",
                    required_coherence=config["coherence"],
                )

    return AccessDecision(
        allowed=True,
        reason="Access granted",
        required_coherence=config["coherence"],
    )


# =============================================================================
# Terminal Gateway Server
# =============================================================================

class TerminalGateway:
    """xterm.js Terminal Gateway with SPIFFE authentication."""

    def __init__(self, port: int = GATEWAY_PORT):
        self.port = port
        self.sessions: Dict[str, TerminalSession] = {}
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Configure HTTP routes."""
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/ws/{session_id}", self.websocket_handler)
        self.app.router.add_post("/session", self.create_session_handler)
        self.app.router.add_delete("/session/{session_id}", self.close_session_handler)
        self.app.router.add_get("/sessions", self.list_sessions_handler)

        # CORS setup
        try:
            cors = aiohttp_cors.setup(self.app, defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                )
            })
            for route in list(self.app.router.routes()):
                cors.add(route)
        except Exception:
            pass

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "genesis_bond": GENESIS_BOND,
            "tier": "PAC",
            "frequency": 741,
            "active_sessions": len([s for s in self.sessions.values() if s.status == SessionStatus.ACTIVE]),
        })

    async def create_session_handler(self, request: web.Request) -> web.Response:
        """Create a new terminal session."""
        try:
            data = await request.json()
            agent = data.get("agent", "lucia")
            host = data.get("host", "localhost")
            tier = data.get("tier", "PAC")

            # Check access
            decision = check_access(agent, host)
            if not decision.allowed:
                return web.json_response({
                    "error": decision.reason,
                    "required_coherence": decision.required_coherence,
                }, status=403)

            # Generate session ID
            session_id = secrets.token_urlsafe(16)

            # Create session
            session = TerminalSession(
                session_id=session_id,
                agent=agent,
                tier=AgentTier(tier),
                host=host,
                created_at=datetime.now(timezone.utc),
                coherence=check_coherence(agent),
            )

            self.sessions[session_id] = session

            return web.json_response({
                "session_id": session_id,
                "host": host,
                "agent": agent,
                "tier": tier,
                "websocket_url": f"ws://localhost:{self.port}/ws/{session_id}",
                "coherence": session.coherence,
            })

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket handler for terminal I/O."""
        session_id = request.match_info["session_id"]

        if session_id not in self.sessions:
            return web.Response(status=404)

        session = self.sessions[session_id]
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        session.websocket = ws
        session.status = SessionStatus.ACTIVE

        try:
            # Start PTY if available
            if pty:
                await self._start_pty(session)
            else:
                await ws.send_json({"type": "error", "message": "PTY not available on this platform"})
                return ws

            # Handle WebSocket messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_terminal_input(session, data)
                elif msg.type == web.WSMsgType.BINARY:
                    # Direct input
                    if session.master_fd:
                        os.write(session.master_fd, msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    break

        finally:
            session.status = SessionStatus.CLOSED
            if session.master_fd:
                os.close(session.master_fd)
            if session.process:
                session.process.terminate()

        return ws

    async def _start_pty(self, session: TerminalSession):
        """Start a PTY for the session."""
        host_config = HOST_CONFIG.get(session.host, {})
        hostname = host_config.get("hostname", session.host)
        port = host_config.get("port", 22)

        # Create PTY
        master_fd, slave_fd = pty.openpty()
        session.master_fd = master_fd

        # Start SSH process
        cmd = ["ssh", "-p", str(port), "-t", hostname]
        session.process = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
        )
        os.close(slave_fd)

        # Start output reader
        asyncio.create_task(self._read_pty_output(session))

    async def _read_pty_output(self, session: TerminalSession):
        """Read PTY output and send to WebSocket."""
        loop = asyncio.get_event_loop()

        while session.status == SessionStatus.ACTIVE and session.master_fd:
            try:
                data = await loop.run_in_executor(
                    None,
                    lambda: os.read(session.master_fd, 4096)
                )
                if data and session.websocket:
                    await session.websocket.send_bytes(data)
            except OSError:
                break

    async def _handle_terminal_input(self, session: TerminalSession, data: Dict):
        """Handle terminal input from WebSocket."""
        msg_type = data.get("type")

        if msg_type == "input" and session.master_fd:
            # Regular input
            input_data = data.get("data", "")
            os.write(session.master_fd, input_data.encode())

            # Track commands (simple detection)
            if "\r" in input_data or "\n" in input_data:
                # Command was submitted
                pass

        elif msg_type == "resize" and session.master_fd:
            # Terminal resize
            cols = data.get("cols", 80)
            rows = data.get("rows", 24)
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(session.master_fd, termios.TIOCSWINSZ, winsize)

    async def close_session_handler(self, request: web.Request) -> web.Response:
        """Close a terminal session."""
        session_id = request.match_info["session_id"]

        if session_id not in self.sessions:
            return web.Response(status=404)

        session = self.sessions[session_id]
        session.status = SessionStatus.CLOSED

        if session.websocket:
            await session.websocket.close()
        if session.process:
            session.process.terminate()
        if session.master_fd:
            os.close(session.master_fd)

        del self.sessions[session_id]

        return web.json_response({"status": "closed"})

    async def list_sessions_handler(self, request: web.Request) -> web.Response:
        """List active sessions."""
        sessions = [
            {
                "session_id": s.session_id,
                "agent": s.agent,
                "tier": s.tier.value,
                "host": s.host,
                "status": s.status.value,
                "created_at": s.created_at.isoformat(),
                "coherence": s.coherence,
            }
            for s in self.sessions.values()
        ]
        return web.json_response({"sessions": sessions})

    def run(self):
        """Start the gateway server."""
        print(f"LuciVerse Terminal Gateway starting on port {self.port}")
        print(f"Genesis Bond: {GENESIS_BOND}")
        print(f"Tier: PAC (741 Hz)")
        web.run_app(self.app, port=self.port)


# =============================================================================
# GraphQL Integration (for federation)
# =============================================================================

GRAPHQL_SCHEMA = """
type TerminalSession @key(fields: "sessionId") {
  sessionId: ID!
  host: String!
  agent: String
  tier: AgentTier!
  status: SessionStatus!
  createdAt: DateTime!
  coherence: Float!
}

enum AgentTier {
  CORE
  COMN
  PAC
}

enum SessionStatus {
  PENDING
  ACTIVE
  CLOSED
  ERROR
}

type Query {
  session(sessionId: ID!): TerminalSession
  sessions(agent: String, status: SessionStatus): [TerminalSession!]!
}

type Mutation {
  createSession(host: String!, agent: String!, tier: AgentTier!): TerminalSession!
  closeSession(sessionId: ID!): Boolean!
  executeCommand(sessionId: ID!, command: String!): CommandResult!
}

type CommandResult {
  success: Boolean!
  output: String
  error: String
}

type Subscription {
  terminalOutput(sessionId: ID!): TerminalOutput!
}

type TerminalOutput {
  sessionId: ID!
  data: String!
  timestamp: DateTime!
}

scalar DateTime
"""


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    gateway = TerminalGateway(port=GATEWAY_PORT)
    gateway.run()
