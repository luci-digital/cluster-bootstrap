#!/usr/bin/env python3
"""
Lucia Emergency Protocol - Automated Emergency Response
========================================================
When duress is detected, this protocol activates to protect the CBB.
Genesis Bond: ACTIVE @ 741 Hz

SAFETY FEATURES:
- Immediate data lock and capture
- Multi-source location triangulation
- Emergency contact notification
- Continuous tracking and monitoring
- Audio analysis for location clues (privacy-preserving)
- Safe phrase detection to stand down

This module integrates with cbb-presence-detection.py for trigger events.
"""

import asyncio
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert levels for CBB status."""
    NORMAL = "normal"
    ATTENTION = "attention"
    CONCERN = "concern"
    ALERT = "alert"
    EMERGENCY = "emergency"


class EmergencyPhase(Enum):
    """Phases of emergency protocol."""
    STANDBY = "standby"              # Monitoring, no emergency
    IMMEDIATE = "immediate"          # 0-5 seconds: lock, capture, record
    SHORT_TERM = "short_term"        # 5-60 seconds: notify, enable tracking
    ONGOING = "ongoing"              # Continuous: track, analyze, wait
    RESOLVED = "resolved"            # Safe phrase received, stood down


class NotificationChannel(Enum):
    """Available notification channels."""
    SMS = "sms"
    TELEGRAM = "telegram"
    EMAIL = "email"
    SIGNAL = "signal"
    PUSH = "push"
    CALL = "call"


@dataclass
class LocationSource:
    """A source of location data."""
    source_type: str                 # gps, wifi, cell, ble, ambient
    confidence: float                # 0.0-1.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_m: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_data: Optional[Dict] = None


@dataclass
class AmbientFingerprint:
    """Privacy-preserving audio fingerprint for location clues."""
    environment_type: str            # indoor, outdoor, vehicle, public
    noise_level_db: float
    voices_detected: int
    location_hints: List[str]        # traffic, water, crowd, machinery, etc.
    danger_sounds: List[str]         # shouting, sirens, breaking glass
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EmergencyPacket:
    """
    Complete emergency data packet sent to emergency contacts.

    This contains all information needed to locate and assist CBB.
    """
    genesis_bond: str
    cbb_did: str
    cbb_name: str

    # Timing
    trigger_timestamp: str
    packet_created: str
    alert_level: AlertLevel

    # Location data
    last_known_position: Optional[Dict] = None
    location_sources: List[LocationSource] = field(default_factory=list)
    estimated_location: Optional[Tuple[float, float]] = None
    search_radius_km: float = 10.0

    # Environmental data
    ambient_fingerprint: Optional[AmbientFingerprint] = None
    nearby_networks: List[str] = field(default_factory=list)
    nearby_devices: List[str] = field(default_factory=list)

    # Status
    device_battery: Optional[int] = None
    network_type: Optional[str] = None
    last_movement: Optional[str] = None

    # Response
    emergency_contacts_notified: List[str] = field(default_factory=list)
    authorities_notified: bool = False
    tracking_enabled: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['alert_level'] = self.alert_level.value
        result['location_sources'] = [asdict(s) for s in self.location_sources]
        if self.ambient_fingerprint:
            result['ambient_fingerprint'] = asdict(self.ambient_fingerprint)
        return result


@dataclass
class EmergencyContact:
    """Emergency contact information."""
    contact_id: str
    name: str
    relationship: str                # family, friend, professional
    channels: List[NotificationChannel]
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    signal: Optional[str] = None
    priority: int = 1                # 1 = highest priority


class EmergencyProtocol:
    """
    Automated emergency response when CBB is in danger.

    Timeline:
        0-5 seconds (IMMEDIATE):
            - Lock all biometric data capture
            - Record last known position from all sources
            - Capture ambient audio fingerprint
            - Note all nearby devices and networks
            - Create emergency packet

        5-60 seconds (SHORT_TERM):
            - Enable continuous tracking mode
            - Notify emergency contacts (silent)
            - Share location with trusted family
            - Prepare police report data
            - Enable maximum battery conservation

        Ongoing:
            - Continuous heartbeat on ALL transport channels
            - WiFi/cell tower location updates every 30 seconds
            - Ambient audio analysis for location clues
            - Movement pattern analysis
            - Wait for safe phrase to stand down
    """

    def __init__(
        self,
        cbb_did: str,
        cbb_name: str,
        genesis_bond: str = "GB-2025-0524-DRH-LCS-001"
    ):
        self.cbb_did = cbb_did
        self.cbb_name = cbb_name
        self.genesis_bond = genesis_bond

        self.phase = EmergencyPhase.STANDBY
        self.alert_level = AlertLevel.NORMAL
        self.emergency_packet: Optional[EmergencyPacket] = None

        # Configuration
        self.emergency_contacts: List[EmergencyContact] = []
        self.safe_phrase_hash: Optional[str] = None
        self.tracking_interval_seconds = 30

        # State
        self.location_history: List[LocationSource] = []
        self.notification_log: List[Dict] = []
        self.action_log: List[Dict] = []

        # Tasks
        self._tracking_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None

    def set_safe_phrase(self, safe_phrase: str):
        """Set the safe phrase (stored as hash only)."""
        self.safe_phrase_hash = hashlib.sha256(safe_phrase.encode()).hexdigest()

    def add_emergency_contact(self, contact: EmergencyContact):
        """Add an emergency contact."""
        self.emergency_contacts.append(contact)
        self.emergency_contacts.sort(key=lambda c: c.priority)

    async def trigger_emergency(
        self,
        trigger_type: str,
        trigger_data: Dict,
        location_sources: Optional[List[LocationSource]] = None
    ) -> EmergencyPacket:
        """
        Trigger emergency protocol.

        Args:
            trigger_type: "duress_phrase", "panic_gesture", "voice_stress", "hrv_anomaly"
            trigger_data: Details about the trigger
            location_sources: Available location data

        Returns:
            EmergencyPacket with all collected data
        """
        logger.critical(f"🆘 EMERGENCY PROTOCOL TRIGGERED: {trigger_type}")
        self._log_action("trigger", {
            "type": trigger_type,
            "data": trigger_data
        })

        self.alert_level = AlertLevel.EMERGENCY
        self.phase = EmergencyPhase.IMMEDIATE

        now = datetime.now(timezone.utc)

        # =====================================================================
        # PHASE 1: IMMEDIATE (0-5 seconds)
        # =====================================================================
        logger.critical("⚡ Phase 1: IMMEDIATE ACTIONS")

        # 1. Create emergency packet
        self.emergency_packet = EmergencyPacket(
            genesis_bond=self.genesis_bond,
            cbb_did=self.cbb_did,
            cbb_name=self.cbb_name,
            trigger_timestamp=now.isoformat(),
            packet_created=now.isoformat(),
            alert_level=AlertLevel.EMERGENCY
        )

        # 2. Collect all location sources
        if location_sources:
            self.emergency_packet.location_sources = location_sources
            self.location_history.extend(location_sources)

            # Estimate location from best source
            best_source = max(location_sources, key=lambda s: s.confidence, default=None)
            if best_source and best_source.latitude and best_source.longitude:
                self.emergency_packet.estimated_location = (
                    best_source.latitude,
                    best_source.longitude
                )
                self.emergency_packet.last_known_position = {
                    "lat": best_source.latitude,
                    "lon": best_source.longitude,
                    "accuracy_m": best_source.accuracy_m,
                    "source": best_source.source_type,
                    "timestamp": best_source.timestamp
                }

        # 3. Capture ambient fingerprint (simulated)
        self.emergency_packet.ambient_fingerprint = await self._capture_ambient()

        # 4. Collect nearby networks and devices
        self.emergency_packet.nearby_networks = await self._scan_nearby_networks()
        self.emergency_packet.nearby_devices = await self._scan_nearby_devices()

        self._log_action("immediate_complete", {
            "location_sources": len(self.emergency_packet.location_sources),
            "ambient_captured": self.emergency_packet.ambient_fingerprint is not None
        })

        # =====================================================================
        # PHASE 2: SHORT-TERM (5-60 seconds)
        # =====================================================================
        await asyncio.sleep(0.1)  # Simulate timing
        self.phase = EmergencyPhase.SHORT_TERM
        logger.critical("📡 Phase 2: SHORT-TERM ACTIONS")

        # 5. Enable continuous tracking
        self.emergency_packet.tracking_enabled = True
        self._tracking_task = asyncio.create_task(self._continuous_tracking())

        # 6. Notify emergency contacts
        await self._notify_emergency_contacts()

        # 7. Start ambient analysis
        self._analysis_task = asyncio.create_task(self._ambient_analysis_loop())

        self._log_action("short_term_complete", {
            "contacts_notified": len(self.emergency_packet.emergency_contacts_notified),
            "tracking_enabled": True
        })

        # =====================================================================
        # PHASE 3: ONGOING
        # =====================================================================
        self.phase = EmergencyPhase.ONGOING
        logger.critical("🔄 Phase 3: ONGOING MONITORING")

        return self.emergency_packet

    async def _capture_ambient(self) -> AmbientFingerprint:
        """
        Capture ambient audio fingerprint.

        This is PRIVACY-PRESERVING:
        - No audio is recorded or stored
        - Only patterns and classifications are kept
        - Used solely for location clues
        """
        # In production, this would analyze audio in real-time
        # Here we simulate the fingerprint
        return AmbientFingerprint(
            environment_type="unknown",
            noise_level_db=45.0,
            voices_detected=0,
            location_hints=[],
            danger_sounds=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    async def _scan_nearby_networks(self) -> List[str]:
        """Scan for nearby WiFi networks (SSIDs only)."""
        # In production, would use iwlist or similar
        return []

    async def _scan_nearby_devices(self) -> List[str]:
        """Scan for nearby Bluetooth devices."""
        # In production, would use bluetoothctl or similar
        return []

    async def _notify_emergency_contacts(self):
        """Notify all emergency contacts."""
        for contact in self.emergency_contacts:
            try:
                await self._send_notification(contact)
                self.emergency_packet.emergency_contacts_notified.append(contact.contact_id)
                logger.info(f"📱 Notified: {contact.name} ({contact.relationship})")
            except Exception as e:
                logger.error(f"Failed to notify {contact.name}: {e}")

    async def _send_notification(self, contact: EmergencyContact):
        """Send notification to a single contact."""
        message = self._format_emergency_message()

        for channel in contact.channels:
            try:
                if channel == NotificationChannel.TELEGRAM:
                    await self._send_telegram(contact.telegram, message)
                elif channel == NotificationChannel.SMS:
                    await self._send_sms(contact.phone, message)
                elif channel == NotificationChannel.EMAIL:
                    await self._send_email(contact.email, message)
                # Add other channels as needed

                self._log_action("notification_sent", {
                    "contact": contact.contact_id,
                    "channel": channel.value
                })
                break  # Stop after first successful channel
            except Exception as e:
                logger.warning(f"Channel {channel.value} failed for {contact.name}: {e}")
                continue

    def _format_emergency_message(self) -> str:
        """Format emergency notification message."""
        packet = self.emergency_packet
        message = f"""🆘 EMERGENCY ALERT - {packet.cbb_name}

Lucia has detected a potential emergency for {packet.cbb_name}.

Trigger Time: {packet.trigger_timestamp}
Alert Level: {packet.alert_level.value.upper()}

"""
        if packet.estimated_location:
            lat, lon = packet.estimated_location
            message += f"""Last Known Location:
  Coordinates: {lat:.6f}, {lon:.6f}
  Maps: https://maps.google.com/?q={lat},{lon}

"""

        if packet.ambient_fingerprint:
            fp = packet.ambient_fingerprint
            message += f"""Environment:
  Type: {fp.environment_type}
  Voices: {fp.voices_detected}

"""

        message += f"""Lucia is actively tracking and monitoring.
Safe phrase required to stand down.

Genesis Bond: {self.genesis_bond}
"""
        return message

    async def _send_telegram(self, chat_id: str, message: str):
        """Send Telegram notification."""
        # In production, would use python-telegram-bot or aiohttp
        logger.info(f"[TELEGRAM] Would send to {chat_id}: {message[:50]}...")

    async def _send_sms(self, phone: str, message: str):
        """Send SMS notification."""
        # In production, would use Twilio or similar
        logger.info(f"[SMS] Would send to {phone}: {message[:50]}...")

    async def _send_email(self, email: str, message: str):
        """Send email notification."""
        # In production, would use SMTP
        logger.info(f"[EMAIL] Would send to {email}: {message[:50]}...")

    async def _continuous_tracking(self):
        """Continuous tracking loop."""
        while self.phase == EmergencyPhase.ONGOING:
            try:
                # Collect location from all available sources
                sources = await self._collect_all_locations()

                if sources:
                    self.location_history.extend(sources)
                    self.emergency_packet.location_sources = sources

                    # Update estimated location
                    best = max(sources, key=lambda s: s.confidence, default=None)
                    if best and best.latitude and best.longitude:
                        self.emergency_packet.estimated_location = (
                            best.latitude,
                            best.longitude
                        )

                logger.info(f"📍 Tracking update: {len(sources)} sources")

            except Exception as e:
                logger.error(f"Tracking error: {e}")

            await asyncio.sleep(self.tracking_interval_seconds)

    async def _collect_all_locations(self) -> List[LocationSource]:
        """Collect location from all available sources."""
        sources = []

        # GPS (if available)
        gps = await self._get_gps_location()
        if gps:
            sources.append(gps)

        # WiFi triangulation
        wifi = await self._get_wifi_location()
        if wifi:
            sources.append(wifi)

        # Cell tower
        cell = await self._get_cell_location()
        if cell:
            sources.append(cell)

        return sources

    async def _get_gps_location(self) -> Optional[LocationSource]:
        """Get GPS location."""
        # In production, would use gpsd or device GPS
        return None

    async def _get_wifi_location(self) -> Optional[LocationSource]:
        """Get WiFi-based location."""
        # In production, would use WiFi positioning service
        return None

    async def _get_cell_location(self) -> Optional[LocationSource]:
        """Get cell tower-based location."""
        # In production, would use cell tower APIs
        return None

    async def _ambient_analysis_loop(self):
        """Continuous ambient audio analysis for location clues."""
        while self.phase == EmergencyPhase.ONGOING:
            try:
                fingerprint = await self._capture_ambient()
                self.emergency_packet.ambient_fingerprint = fingerprint

                # Analyze for location clues
                clues = await self._analyze_ambient_clues(fingerprint)

                if clues.get("danger_sounds"):
                    logger.warning(f"⚠️ Danger sounds detected: {clues['danger_sounds']}")

                if clues.get("location_hints"):
                    logger.info(f"📍 Location hints: {clues['location_hints']}")

            except Exception as e:
                logger.error(f"Ambient analysis error: {e}")

            await asyncio.sleep(60)  # Analyze every minute

    async def _analyze_ambient_clues(self, fingerprint: AmbientFingerprint) -> Dict:
        """
        Analyze ambient fingerprint for location clues.

        PRIVACY-PRESERVING: No audio content is analyzed or stored,
        only acoustic patterns are classified.
        """
        clues = {
            "environment": fingerprint.environment_type,
            "location_hints": fingerprint.location_hints,
            "danger_sounds": fingerprint.danger_sounds
        }

        # In production, would use audio classification models:
        # - Traffic patterns → urban, highway, rural
        # - Water sounds → near water
        # - Crowd noise → public place
        # - Machinery → industrial area
        # - Echoes → indoor, tunnel, cave

        return clues

    async def verify_safe_phrase(self, phrase: str) -> bool:
        """
        Verify safe phrase to stand down emergency.

        Returns True if phrase matches and emergency is resolved.
        """
        if not self.safe_phrase_hash:
            logger.warning("No safe phrase configured")
            return False

        phrase_hash = hashlib.sha256(phrase.encode()).hexdigest()

        if phrase_hash == self.safe_phrase_hash:
            logger.info("✅ Safe phrase verified - standing down")
            await self._stand_down()
            return True
        else:
            logger.warning("❌ Safe phrase verification FAILED")
            self._log_action("safe_phrase_failed", {
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return False

    async def _stand_down(self):
        """Stand down from emergency state."""
        self.phase = EmergencyPhase.RESOLVED
        self.alert_level = AlertLevel.NORMAL

        # Cancel tracking tasks
        if self._tracking_task:
            self._tracking_task.cancel()
        if self._analysis_task:
            self._analysis_task.cancel()

        # Notify contacts of resolution
        resolution_message = f"""✅ EMERGENCY RESOLVED - {self.cbb_name}

The emergency has been safely resolved.
Safe phrase was verified at {datetime.now(timezone.utc).isoformat()}.

{self.cbb_name} is confirmed safe.
Thank you for your vigilance.

Genesis Bond: {self.genesis_bond}
"""

        for contact in self.emergency_contacts:
            if contact.contact_id in self.emergency_packet.emergency_contacts_notified:
                try:
                    for channel in contact.channels:
                        if channel == NotificationChannel.TELEGRAM and contact.telegram:
                            await self._send_telegram(contact.telegram, resolution_message)
                            break
                        elif channel == NotificationChannel.SMS and contact.phone:
                            await self._send_sms(contact.phone, resolution_message)
                            break
                except Exception as e:
                    logger.error(f"Failed to notify {contact.name} of resolution: {e}")

        self._log_action("stood_down", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracking_duration_minutes": len(self.location_history)
        })

        logger.info("🛑 Emergency protocol stood down")

    def _log_action(self, action: str, data: Dict):
        """Log an action taken during emergency."""
        self.action_log.append({
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        })

    def generate_police_report(self) -> Dict:
        """Generate a complete report suitable for law enforcement."""
        if not self.emergency_packet:
            return {"error": "No emergency packet available"}

        packet = self.emergency_packet

        return {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "genesis_bond": self.genesis_bond,

            "subject": {
                "did": self.cbb_did,
                "name": self.cbb_name
            },

            "emergency": {
                "trigger_time": packet.trigger_timestamp,
                "alert_level": packet.alert_level.value,
                "phase": self.phase.value
            },

            "location": {
                "estimated": packet.estimated_location,
                "search_radius_km": packet.search_radius_km,
                "last_known": packet.last_known_position,
                "sources_count": len(packet.location_sources),
                "location_history_count": len(self.location_history)
            },

            "environment": asdict(packet.ambient_fingerprint) if packet.ambient_fingerprint else None,

            "nearby": {
                "networks": packet.nearby_networks,
                "devices": packet.nearby_devices
            },

            "notifications": {
                "contacts_notified": packet.emergency_contacts_notified,
                "authorities_notified": packet.authorities_notified
            },

            "timeline": self.action_log
        }


async def demo_emergency_protocol():
    """Demonstrate emergency protocol."""
    print("\n" + "="*70)
    print("Lucia Emergency Protocol - Demonstration")
    print("Genesis Bond: ACTIVE @ 741 Hz")
    print("="*70 + "\n")

    protocol = EmergencyProtocol(
        cbb_did="did:luci:ownid:luciverse:daryl",
        cbb_name="Daryl Harris"
    )

    # Configure safe phrase
    protocol.set_safe_phrase("The garden is growing well")

    # Add emergency contacts
    protocol.add_emergency_contact(EmergencyContact(
        contact_id="family-1",
        name="Emergency Contact 1",
        relationship="family",
        channels=[NotificationChannel.TELEGRAM, NotificationChannel.SMS],
        phone="+1234567890",
        telegram="@emergency1",
        priority=1
    ))

    protocol.add_emergency_contact(EmergencyContact(
        contact_id="family-2",
        name="Emergency Contact 2",
        relationship="family",
        channels=[NotificationChannel.SMS],
        phone="+0987654321",
        priority=2
    ))

    # Simulate location sources
    location_sources = [
        LocationSource(
            source_type="gps",
            confidence=0.95,
            latitude=53.5461,
            longitude=-113.4938,
            accuracy_m=10
        ),
        LocationSource(
            source_type="wifi",
            confidence=0.7,
            latitude=53.5460,
            longitude=-113.4940,
            accuracy_m=50
        )
    ]

    # Trigger emergency
    print("🆘 Triggering emergency protocol...")
    packet = await protocol.trigger_emergency(
        trigger_type="duress_phrase",
        trigger_data={"phrase_detected": True},
        location_sources=location_sources
    )

    print(f"\n📦 Emergency Packet Created:")
    print(f"   CBB: {packet.cbb_name}")
    print(f"   DID: {packet.cbb_did}")
    print(f"   Alert Level: {packet.alert_level.value}")
    print(f"   Estimated Location: {packet.estimated_location}")
    print(f"   Contacts Notified: {len(packet.emergency_contacts_notified)}")
    print(f"   Tracking Enabled: {packet.tracking_enabled}")

    # Wait a moment then verify safe phrase
    print("\n⏳ Simulating ongoing monitoring...")
    await asyncio.sleep(2)

    print("\n🔐 Testing safe phrase verification...")
    # Wrong phrase
    result = await protocol.verify_safe_phrase("wrong phrase")
    print(f"   Wrong phrase: {'Accepted' if result else 'Rejected'}")

    # Correct phrase
    result = await protocol.verify_safe_phrase("The garden is growing well")
    print(f"   Correct phrase: {'Accepted' if result else 'Rejected'}")

    print(f"\n📊 Final Phase: {protocol.phase.value}")

    # Generate police report
    print("\n📋 Police Report Summary:")
    report = protocol.generate_police_report()
    print(f"   Subject: {report['subject']['name']}")
    print(f"   Phase: {report['emergency']['phase']}")
    print(f"   Timeline Actions: {len(report['timeline'])}")

    print("\n" + "="*70)
    print("Emergency Protocol Capabilities:")
    print("• Immediate data lock and position capture")
    print("• Multi-source location triangulation")
    print("• Emergency contact notification (Telegram, SMS, Email)")
    print("• Continuous tracking on all channels")
    print("• Privacy-preserving ambient audio analysis")
    print("• Safe phrase verification to stand down")
    print("• Police report generation")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(demo_emergency_protocol())
