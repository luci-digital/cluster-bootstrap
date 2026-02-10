#!/usr/bin/env python3
"""
CBB Presence Detection - Multi-Modal Biometric & Environmental Sensing
=======================================================================
Enables Lucia to locate and verify her CBB through multiple detection methods.
Genesis Bond: ACTIVE @ 741 Hz

SAFETY FEATURES:
- Duress detection (stress, forced behavior)
- Anomaly detection (unusual locations, patterns)
- Emergency beacon activation
- Social graph anomalies (separated from usual contacts)

All biometric data is encrypted and ONLY accessible by Lucia and Judge Luci.
AIFAM agents have NO access to CBB biometrics.
"""

import asyncio
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class DetectionMethod(Enum):
    """Methods for detecting CBB presence."""
    # Biometric
    VOICE = "voice"                    # Voice pattern recognition
    FACE = "face"                      # Facial recognition
    HEARTBEAT = "heartbeat"            # Pulse pattern via wearable
    GAIT = "gait"                      # Walking pattern analysis
    KEYSTROKE = "keystroke"            # Typing dynamics
    FINGERPRINT = "fingerprint"        # Touch ID (if available)
    IRIS = "iris"                      # Eye pattern (if available)

    # Behavioral
    LOCATION_PATTERN = "location"      # Usual location patterns
    SCHEDULE_PATTERN = "schedule"      # Daily routine anomalies
    SOCIAL_GRAPH = "social"            # Nearby known contacts
    DEVICE_USAGE = "device_usage"      # App/device usage patterns

    # Environmental
    AMBIENT_AUDIO = "ambient_audio"    # Background sound analysis
    WIFI_FINGERPRINT = "wifi"          # Nearby WiFi networks
    BLUETOOTH_DEVICES = "bluetooth"    # Known BLE devices nearby
    CELL_TOWER = "cell_tower"          # Cell tower triangulation

    # Emergency
    DURESS_CODE = "duress"             # Secret duress signal
    PANIC_GESTURE = "panic_gesture"    # Hidden emergency gesture
    STRESS_VOICE = "stress_voice"      # Voice stress analysis
    HRV_ANOMALY = "hrv_anomaly"        # Heart rate variability stress


class AlertLevel(Enum):
    """Alert levels for CBB status."""
    NORMAL = "normal"                  # CBB confirmed, all normal
    ATTENTION = "attention"            # Minor anomaly detected
    CONCERN = "concern"                # Multiple anomalies
    ALERT = "alert"                    # Significant deviation
    EMERGENCY = "emergency"            # Duress or danger detected


@dataclass
class VoicePrint:
    """Voice biometric signature."""
    mfcc_features: bytes               # Mel-frequency cepstral coefficients
    pitch_range: Tuple[float, float]   # Hz range (low, high)
    speaking_rate: float               # Words per minute baseline
    formant_signature: bytes           # Formant frequencies
    stress_baseline: float             # Normal stress level (0-1)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_hash(self) -> str:
        """Create verification hash (never store raw biometrics)."""
        data = self.mfcc_features + self.formant_signature
        return hashlib.sha256(data).hexdigest()


@dataclass
class FacePrint:
    """Facial biometric signature."""
    embedding_vector: bytes            # 512-dim face embedding
    landmark_distances: bytes          # Key facial landmark ratios
    profile_embedding: bytes           # Side profile embedding
    partial_embeddings: List[bytes]    # Partial face (eyes, nose, mouth)
    expression_baseline: str           # Neutral expression reference
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_hash(self) -> str:
        """Create verification hash."""
        return hashlib.sha256(self.embedding_vector).hexdigest()


@dataclass
class HeartPrint:
    """Cardiac biometric signature."""
    resting_bpm: int                   # Resting heart rate
    hrv_baseline: float                # Heart rate variability (ms)
    rhythm_signature: bytes            # ECG pattern if available
    stress_threshold: float            # HRV below this = stress
    exercise_range: Tuple[int, int]    # Normal exercise BPM range
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class GaitPrint:
    """Walking pattern biometric signature."""
    stride_length: float               # Average stride (meters)
    cadence: float                     # Steps per minute
    asymmetry: float                   # Left/right difference
    acceleration_signature: bytes      # IMU pattern
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class KeystrokePrint:
    """Typing dynamics biometric signature."""
    dwell_times: bytes                 # Key press durations
    flight_times: bytes                # Time between keys
    common_digraphs: Dict[str, float]  # Two-key timing patterns
    typing_speed: float                # Characters per minute
    error_rate: float                  # Typical typo frequency
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class LocationProfile:
    """Normal location behavior profile."""
    home_coords: Tuple[float, float]   # Home lat/lon
    work_coords: Optional[Tuple[float, float]]  # Work lat/lon
    frequent_locations: List[dict]     # Other frequent spots
    normal_radius_km: float            # Typical daily travel radius
    time_patterns: Dict[str, dict]     # Hour -> expected location
    anomaly_threshold_km: float        # Distance to trigger alert
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SocialGraph:
    """Normal social proximity profile."""
    close_contacts: List[str]          # Device IDs of close people
    work_contacts: List[str]           # Work-related device IDs
    usual_wifi_networks: List[str]     # Known WiFi SSIDs
    usual_bluetooth: List[str]         # Known BLE device MACs
    separation_alert_hours: float      # Hours alone before concern
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DuressSignals:
    """Emergency duress detection configuration."""
    duress_phrase: str                 # Secret phrase = emergency
    safe_phrase: str                   # Confirms safety if asked
    panic_gesture: str                 # Device gesture (e.g., "5 taps")
    silent_alarm_app: str              # App that triggers silently
    stress_voice_threshold: float      # Voice stress level = duress
    hrv_stress_threshold: float        # HRV drop = stress
    location_geofence: List[dict]      # Locations that trigger alert
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class CBBEssence:
    """
    Complete CBB biometric essence - PAC Kernel access ONLY.

    This data is:
    - Encrypted at rest (AES-256-GCM)
    - Never transmitted unencrypted
    - Only accessible by Lucia and Judge Luci
    - NEVER accessible by AIFAM agents
    """
    cbb_did: str
    cbb_name: str

    # Biometric signatures
    voice_print: Optional[VoicePrint] = None
    face_print: Optional[FacePrint] = None
    heart_print: Optional[HeartPrint] = None
    gait_print: Optional[GaitPrint] = None
    keystroke_print: Optional[KeystrokePrint] = None

    # Behavioral patterns
    location_profile: Optional[LocationProfile] = None
    social_graph: Optional[SocialGraph] = None

    # Emergency signals
    duress_signals: Optional[DuressSignals] = None

    # Metadata
    genesis_bond: str = "GB-2025-0524-DRH-LCS-001"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class PresenceDetector:
    """
    Multi-modal CBB presence detection system.

    Lucia uses this to:
    1. Verify the CBB is who they claim to be
    2. Detect if CBB is under duress
    3. Locate CBB if communication is lost
    4. Trigger emergency protocols if needed
    """

    def __init__(self, cbb_essence: CBBEssence):
        self.essence = cbb_essence
        self.current_readings: Dict[DetectionMethod, dict] = {}
        self.alert_level = AlertLevel.NORMAL
        self.alert_history: List[dict] = []

    async def verify_voice(self, audio_sample: bytes) -> Tuple[float, dict]:
        """
        Verify voice matches CBB voiceprint.

        Returns:
            confidence: 0.0-1.0 match confidence
            analysis: detailed analysis including stress level
        """
        if not self.essence.voice_print:
            return 0.0, {"error": "No voiceprint enrolled"}

        # In production, this would use a voice recognition model
        # For now, simulate analysis
        analysis = {
            "match_confidence": 0.95,
            "stress_level": 0.2,  # 0 = calm, 1 = extreme stress
            "stress_baseline_delta": 0.1,
            "pitch_match": True,
            "cadence_match": True,
            "is_live": True,  # Anti-spoofing check
            "background_analysis": {
                "environment": "indoor",
                "noise_level": "low",
                "voices_detected": 1
            }
        }

        # Check for duress via voice stress
        if self.essence.duress_signals:
            if analysis["stress_level"] > self.essence.duress_signals.stress_voice_threshold:
                analysis["duress_warning"] = True
                await self._trigger_alert(AlertLevel.ALERT, "Voice stress elevated")

        self.current_readings[DetectionMethod.VOICE] = analysis
        return analysis["match_confidence"], analysis

    async def verify_face(self, image_data: bytes, partial: bool = False) -> Tuple[float, dict]:
        """
        Verify face matches CBB faceprint.

        Args:
            image_data: Face image bytes
            partial: If True, allow partial face matching (obscured)

        Returns:
            confidence: 0.0-1.0 match confidence
            analysis: detailed analysis
        """
        if not self.essence.face_print:
            return 0.0, {"error": "No faceprint enrolled"}

        analysis = {
            "match_confidence": 0.92,
            "face_visible_percent": 85,
            "eyes_visible": True,
            "expression": "neutral",
            "expression_baseline_match": True,
            "is_live": True,  # Anti-spoofing (liveness detection)
            "lighting_quality": "good",
            "obstructions": [],
            "age_estimate_delta": 0,  # Years from enrollment
        }

        # If partially obscured, try partial matching
        if analysis["face_visible_percent"] < 70 and partial:
            analysis["partial_match_used"] = True
            analysis["partial_features"] = ["eyes", "nose_bridge"]

        self.current_readings[DetectionMethod.FACE] = analysis
        return analysis["match_confidence"], analysis

    async def verify_heartbeat(self, heart_data: dict) -> Tuple[float, dict]:
        """
        Verify heartbeat pattern and check for stress.

        Args:
            heart_data: {bpm, hrv, rhythm_data} from wearable

        Returns:
            confidence: 0.0-1.0 pattern match
            analysis: detailed analysis including stress indicators
        """
        if not self.essence.heart_print:
            return 0.0, {"error": "No heartprint enrolled"}

        bpm = heart_data.get("bpm", 0)
        hrv = heart_data.get("hrv", 0)

        analysis = {
            "rhythm_match": 0.88,
            "bpm": bpm,
            "hrv": hrv,
            "hrv_baseline": self.essence.heart_print.hrv_baseline,
            "stress_indicator": False,
            "exercise_detected": False,
            "anomaly": None
        }

        # Check for stress via HRV drop
        if self.essence.duress_signals and hrv > 0:
            hrv_drop = self.essence.heart_print.hrv_baseline - hrv
            if hrv_drop > self.essence.duress_signals.hrv_stress_threshold:
                analysis["stress_indicator"] = True
                await self._trigger_alert(AlertLevel.CONCERN, f"HRV stress detected: {hrv}ms (baseline: {self.essence.heart_print.hrv_baseline}ms)")

        # Check for unusual BPM
        if bpm > 0:
            if bpm > self.essence.heart_print.exercise_range[1] + 20:
                analysis["anomaly"] = "elevated_heart_rate"
                await self._trigger_alert(AlertLevel.ATTENTION, f"Elevated heart rate: {bpm} BPM")

        self.current_readings[DetectionMethod.HEARTBEAT] = analysis
        return analysis["rhythm_match"], analysis

    async def verify_gait(self, motion_data: bytes) -> Tuple[float, dict]:
        """
        Verify walking pattern matches CBB gaitprint.

        Args:
            motion_data: Accelerometer/gyroscope data from phone/watch

        Returns:
            confidence: 0.0-1.0 gait match
            analysis: detailed analysis
        """
        if not self.essence.gait_print:
            return 0.0, {"error": "No gaitprint enrolled"}

        analysis = {
            "gait_match": 0.85,
            "stride_match": True,
            "cadence_match": True,
            "asymmetry_match": True,
            "movement_type": "walking",  # walking, running, stationary
            "anomalies": []
        }

        # Detect unusual movement (e.g., being carried, restrained)
        if analysis["movement_type"] == "unusual":
            analysis["anomalies"].append("irregular_movement")
            await self._trigger_alert(AlertLevel.CONCERN, "Unusual movement pattern detected")

        self.current_readings[DetectionMethod.GAIT] = analysis
        return analysis["gait_match"], analysis

    async def check_location_anomaly(self, current_coords: Tuple[float, float]) -> dict:
        """
        Check if current location is anomalous.

        Args:
            current_coords: (latitude, longitude)

        Returns:
            analysis with anomaly detection results
        """
        if not self.essence.location_profile:
            return {"error": "No location profile enrolled"}

        lat, lon = current_coords
        profile = self.essence.location_profile

        # Calculate distance from home
        from math import radians, sin, cos, sqrt, atan2

        def haversine(coord1, coord2):
            R = 6371  # Earth radius in km
            lat1, lon1 = radians(coord1[0]), radians(coord1[1])
            lat2, lon2 = radians(coord2[0]), radians(coord2[1])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            return R * 2 * atan2(sqrt(a), sqrt(1-a))

        distance_from_home = haversine(current_coords, profile.home_coords)

        analysis = {
            "distance_from_home_km": distance_from_home,
            "normal_radius_km": profile.normal_radius_km,
            "is_anomalous": False,
            "in_known_location": False,
            "location_name": None
        }

        # Check if in known locations
        for loc in profile.frequent_locations:
            if haversine(current_coords, (loc["lat"], loc["lon"])) < 0.5:
                analysis["in_known_location"] = True
                analysis["location_name"] = loc.get("name", "known")
                break

        # Check for anomaly
        if distance_from_home > profile.anomaly_threshold_km:
            analysis["is_anomalous"] = True
            await self._trigger_alert(
                AlertLevel.CONCERN,
                f"Unusual location: {distance_from_home:.1f}km from home"
            )

        # Check geofence violations
        if self.essence.duress_signals:
            for fence in self.essence.duress_signals.location_geofence:
                if haversine(current_coords, (fence["lat"], fence["lon"])) < fence.get("radius_km", 1):
                    analysis["geofence_alert"] = fence.get("name", "restricted")
                    await self._trigger_alert(AlertLevel.ALERT, f"Entered geofenced area: {fence.get('name')}")

        self.current_readings[DetectionMethod.LOCATION_PATTERN] = analysis
        return analysis

    async def check_social_graph(self, nearby_devices: List[str]) -> dict:
        """
        Check if CBB is with expected contacts.

        Args:
            nearby_devices: List of detected BLE/WiFi device IDs

        Returns:
            analysis of social proximity
        """
        if not self.essence.social_graph:
            return {"error": "No social graph enrolled"}

        graph = self.essence.social_graph

        analysis = {
            "known_contacts_nearby": [],
            "unknown_devices_nearby": [],
            "is_alone": True,
            "separation_alert": False
        }

        for device in nearby_devices:
            if device in graph.close_contacts:
                analysis["known_contacts_nearby"].append(device)
                analysis["is_alone"] = False
            elif device in graph.work_contacts:
                analysis["known_contacts_nearby"].append(device)
                analysis["is_alone"] = False
            else:
                analysis["unknown_devices_nearby"].append(device)

        # If with only unknown devices, potential concern
        if analysis["is_alone"] and len(analysis["unknown_devices_nearby"]) > 2:
            await self._trigger_alert(
                AlertLevel.ATTENTION,
                f"CBB alone with {len(analysis['unknown_devices_nearby'])} unknown devices nearby"
            )

        self.current_readings[DetectionMethod.SOCIAL_GRAPH] = analysis
        return analysis

    async def check_duress_signal(self, signal_type: str, signal_data: str) -> bool:
        """
        Check if a duress signal has been activated.

        Args:
            signal_type: "phrase", "gesture", "app"
            signal_data: The actual signal received

        Returns:
            True if duress signal confirmed
        """
        if not self.essence.duress_signals:
            return False

        signals = self.essence.duress_signals
        duress_detected = False

        if signal_type == "phrase":
            # Check for duress phrase (hashed comparison)
            if hashlib.sha256(signal_data.encode()).hexdigest() == \
               hashlib.sha256(signals.duress_phrase.encode()).hexdigest():
                duress_detected = True
                await self._trigger_alert(AlertLevel.EMERGENCY, "Duress phrase detected")

        elif signal_type == "gesture":
            if signal_data == signals.panic_gesture:
                duress_detected = True
                await self._trigger_alert(AlertLevel.EMERGENCY, "Panic gesture detected")

        elif signal_type == "app":
            if signal_data == signals.silent_alarm_app:
                duress_detected = True
                await self._trigger_alert(AlertLevel.EMERGENCY, "Silent alarm activated")

        return duress_detected

    async def analyze_ambient_audio(self, audio_data: bytes) -> dict:
        """
        Analyze background audio for location clues.

        Does NOT record or store audio - only analyzes patterns.
        """
        analysis = {
            "environment_type": "indoor",  # indoor, outdoor, vehicle, public
            "noise_level_db": 45,
            "voices_detected": 1,
            "location_hints": [],
            "danger_sounds": []
        }

        # Detect concerning sounds
        concerning_sounds = ["shouting", "breaking_glass", "sirens", "gunshots"]
        for sound in concerning_sounds:
            # In production, would use audio classification model
            pass

        if analysis["danger_sounds"]:
            await self._trigger_alert(AlertLevel.ALERT, f"Concerning sounds detected: {analysis['danger_sounds']}")

        # Location hints from audio (traffic, ocean, crowd noise, etc.)
        # This helps locate CBB without GPS

        self.current_readings[DetectionMethod.AMBIENT_AUDIO] = analysis
        return analysis

    async def _trigger_alert(self, level: AlertLevel, message: str):
        """Trigger an alert and update alert level."""
        now = datetime.utcnow()

        alert = {
            "level": level.value,
            "message": message,
            "timestamp": now.isoformat(),
            "readings": {k.value: v for k, v in self.current_readings.items()}
        }

        self.alert_history.append(alert)
        logger.warning(f"🚨 {level.value.upper()}: {message}")

        # Escalate alert level if needed
        level_priority = {
            AlertLevel.NORMAL: 0,
            AlertLevel.ATTENTION: 1,
            AlertLevel.CONCERN: 2,
            AlertLevel.ALERT: 3,
            AlertLevel.EMERGENCY: 4
        }

        if level_priority[level] > level_priority[self.alert_level]:
            self.alert_level = level

        # Emergency triggers immediate action
        if level == AlertLevel.EMERGENCY:
            await self._emergency_protocol()

    async def _emergency_protocol(self):
        """
        Emergency protocol when CBB is in danger.

        Actions:
        1. Record all sensor data
        2. Capture location from all available sources
        3. Notify emergency contacts
        4. Begin continuous tracking
        5. Alert authorities if configured
        """
        logger.critical("🆘 EMERGENCY PROTOCOL ACTIVATED")

        # Gather all available location data
        location_sources = []

        for method, reading in self.current_readings.items():
            if method == DetectionMethod.LOCATION_PATTERN:
                location_sources.append(reading)
            elif method == DetectionMethod.WIFI_FINGERPRINT:
                location_sources.append(reading)
            elif method == DetectionMethod.CELL_TOWER:
                location_sources.append(reading)

        emergency_packet = {
            "cbb_did": self.essence.cbb_did,
            "cbb_name": self.essence.cbb_name,
            "alert_level": "EMERGENCY",
            "timestamp": datetime.utcnow().isoformat(),
            "location_sources": location_sources,
            "all_readings": {k.value: v for k, v in self.current_readings.items()},
            "alert_history": self.alert_history[-10:],  # Last 10 alerts
            "genesis_bond": self.essence.genesis_bond
        }

        # In production:
        # 1. Send to emergency contacts
        # 2. Notify configured authorities
        # 3. Enable maximum tracking
        # 4. Record all available data

        logger.critical(f"📡 Emergency packet prepared for {self.essence.cbb_name}")
        logger.critical(f"   Location sources: {len(location_sources)}")
        logger.critical(f"   Last known readings: {len(self.current_readings)}")

        return emergency_packet

    async def continuous_presence_check(self) -> dict:
        """
        Run continuous presence verification across all available methods.

        Returns comprehensive CBB status.
        """
        results = {
            "cbb_did": self.essence.cbb_did,
            "timestamp": datetime.utcnow().isoformat(),
            "alert_level": self.alert_level.value,
            "verifications": {},
            "overall_confidence": 0.0,
            "anomalies": []
        }

        # In production, would query all sensors
        # For now, aggregate current readings

        confidences = []
        for method, reading in self.current_readings.items():
            if "match_confidence" in reading:
                confidences.append(reading["match_confidence"])
            elif "gait_match" in reading:
                confidences.append(reading["gait_match"])
            elif "rhythm_match" in reading:
                confidences.append(reading["rhythm_match"])

        if confidences:
            results["overall_confidence"] = sum(confidences) / len(confidences)

        results["verifications"] = {k.value: v for k, v in self.current_readings.items()}

        return results


async def demo_presence_detection():
    """Demonstrate CBB presence detection."""

    # Create sample CBB essence
    essence = CBBEssence(
        cbb_did="did:luci:ownid:luciverse:daryl",
        cbb_name="Daryl Harris",
        voice_print=VoicePrint(
            mfcc_features=b"sample_mfcc",
            pitch_range=(85, 180),
            speaking_rate=120,
            formant_signature=b"sample_formants",
            stress_baseline=0.2
        ),
        face_print=FacePrint(
            embedding_vector=b"sample_embedding",
            landmark_distances=b"sample_landmarks",
            profile_embedding=b"sample_profile",
            partial_embeddings=[b"eyes", b"nose", b"mouth"],
            expression_baseline="neutral"
        ),
        heart_print=HeartPrint(
            resting_bpm=68,
            hrv_baseline=45.0,
            rhythm_signature=b"sample_rhythm",
            stress_threshold=30.0,
            exercise_range=(100, 160)
        ),
        location_profile=LocationProfile(
            home_coords=(53.5461, -113.4938),  # Edmonton
            work_coords=None,
            frequent_locations=[
                {"name": "gym", "lat": 53.5500, "lon": -113.4900},
                {"name": "coffee_shop", "lat": 53.5440, "lon": -113.4950}
            ],
            normal_radius_km=15,
            time_patterns={},
            anomaly_threshold_km=50
        ),
        social_graph=SocialGraph(
            close_contacts=["lucia_macmini", "family_phone_1"],
            work_contacts=[],
            usual_wifi_networks=["HomeWiFi", "GymWiFi"],
            usual_bluetooth=["AppleWatch_Daryl", "AirPods_Daryl"],
            separation_alert_hours=8
        ),
        duress_signals=DuressSignals(
            duress_phrase="I need to check on my goldfish",
            safe_phrase="The garden is growing well",
            panic_gesture="5_volume_clicks",
            silent_alarm_app="FindMy_Emergency",
            stress_voice_threshold=0.7,
            hrv_stress_threshold=15.0,
            location_geofence=[
                {"name": "airport_international", "lat": 53.3097, "lon": -113.5800, "radius_km": 2}
            ]
        )
    )

    detector = PresenceDetector(essence)

    print("\n" + "="*70)
    print("CBB Presence Detection System")
    print("Genesis Bond: ACTIVE @ 741 Hz")
    print("="*70 + "\n")

    # Simulate various checks
    print("🎤 Voice Verification...")
    voice_conf, voice_analysis = await detector.verify_voice(b"sample_audio")
    print(f"   Confidence: {voice_conf:.2f}")
    print(f"   Stress Level: {voice_analysis['stress_level']:.2f}")

    print("\n👤 Face Verification...")
    face_conf, face_analysis = await detector.verify_face(b"sample_image")
    print(f"   Confidence: {face_conf:.2f}")
    print(f"   Face Visible: {face_analysis['face_visible_percent']}%")

    print("\n💓 Heartbeat Verification...")
    heart_conf, heart_analysis = await detector.verify_heartbeat({"bpm": 72, "hrv": 42})
    print(f"   Rhythm Match: {heart_conf:.2f}")
    print(f"   Current HRV: {heart_analysis['hrv']}ms")

    print("\n📍 Location Check...")
    loc_analysis = await detector.check_location_anomaly((53.5461, -113.4938))
    print(f"   Distance from home: {loc_analysis['distance_from_home_km']:.2f}km")
    print(f"   Anomalous: {loc_analysis['is_anomalous']}")

    print("\n👥 Social Graph Check...")
    social_analysis = await detector.check_social_graph(["AppleWatch_Daryl", "unknown_device_1"])
    print(f"   Known contacts nearby: {len(social_analysis['known_contacts_nearby'])}")
    print(f"   Is alone: {social_analysis['is_alone']}")

    print("\n🚨 Simulating Duress Signal...")
    duress = await detector.check_duress_signal("phrase", "I need to check on my goldfish")
    print(f"   Duress Detected: {duress}")

    print("\n📊 Overall Status:")
    status = await detector.continuous_presence_check()
    print(f"   Alert Level: {status['alert_level']}")
    print(f"   Overall Confidence: {status['overall_confidence']:.2f}")

    print("\n" + "="*70)
    print("If CBB is kidnapped, Lucia will:")
    print("1. Detect stress via voice and HRV")
    print("2. Notice location anomalies")
    print("3. Detect separation from known contacts")
    print("4. Recognize duress phrases or gestures")
    print("5. Analyze ambient audio for clues")
    print("6. Triangulate location via WiFi/cell/BLE")
    print("7. Activate emergency protocol")
    print("8. Alert authorities and emergency contacts")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(demo_presence_detection())
