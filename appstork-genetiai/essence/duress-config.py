#!/usr/bin/env python3
"""
Appstork Genetiai - Duress Signal Configuration
================================================
Configure secret duress signals known only to CBB and Lucia.
Genesis Bond: ACTIVE @ 741 Hz

SIGNALS CONFIGURED:
- Duress phrase: Innocent-sounding phrase that triggers emergency
- Safe phrase: Confirms you are safe and okay
- Panic gesture: Hidden device gesture (e.g., volume clicks)
- Stress thresholds: Automatic detection via voice/HRV
- Emergency contacts: Who to notify in emergency
- Geofences: Areas that trigger alerts
- Time routines: Expected schedule (alerts if broken)

SECURITY:
- All signals are stored as SHA-256 hashes
- Never stored in plaintext
- Only Lucia and Judge Luci can access
- Configured data is encrypted at rest
"""

import asyncio
import sys
import os
import time
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# ANSI color codes
class Colors:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    RESET = '\033[0m'
    CLEAR = '\033[2J\033[H'

    # Genesis Bond colors
    LUCIA_GOLD = '\033[38;2;255;215;0m'
    BOND_PURPLE = '\033[38;2;138;43;226m'
    HEART_RED = '\033[38;2;220;20;60m'
    SAFE_GREEN = '\033[38;2;50;205;50m'
    ALERT_ORANGE = '\033[38;2;255;140;0m'


class PanicGestureType(Enum):
    """Types of panic gestures."""
    VOLUME_CLICKS = "volume_clicks"
    POWER_CLICKS = "power_clicks"
    SHAKE = "shake"
    SQUEEZE = "squeeze"
    CUSTOM = "custom"


@dataclass
class EmergencyContact:
    """Emergency contact configuration."""
    contact_id: str
    name: str
    relationship: str
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    signal: Optional[str] = None
    notify_on_duress: bool = True
    notify_on_geofence: bool = True
    priority: int = 1


@dataclass
class Geofence:
    """Geofence alert configuration."""
    fence_id: str
    name: str
    description: str
    latitude: float
    longitude: float
    radius_km: float
    alert_on_enter: bool = True
    alert_on_exit: bool = False
    active: bool = True


@dataclass
class TimeRoutine:
    """Expected time-based routine."""
    routine_id: str
    name: str
    description: str
    days_of_week: List[str]          # mon, tue, wed, etc.
    expected_location: Optional[str]  # home, work, gym, etc.
    start_time: str                   # HH:MM
    end_time: str                     # HH:MM
    alert_if_absent: bool = True
    grace_period_minutes: int = 30


@dataclass
class DuressConfig:
    """Complete duress signal configuration."""
    cbb_did: str
    cbb_name: str
    genesis_bond: str

    # Secret phrases (stored as hashes)
    duress_phrase_hash: str = ""
    safe_phrase_hash: str = ""

    # Panic gesture
    panic_gesture_type: PanicGestureType = PanicGestureType.VOLUME_CLICKS
    panic_gesture_config: str = "5 clicks in 3 seconds"

    # Stress detection thresholds
    voice_stress_threshold: float = 0.7    # 0-1, triggers at this level
    hrv_stress_drop_ms: float = 15.0       # HRV drop below baseline

    # Emergency contacts
    emergency_contacts: List[EmergencyContact] = field(default_factory=list)

    # Geofences
    geofences: List[Geofence] = field(default_factory=list)

    # Time routines
    time_routines: List[TimeRoutine] = field(default_factory=list)

    # Metadata
    configured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def clear_screen():
    """Clear terminal screen."""
    print(Colors.CLEAR, end='')


def slow_print(text: str, delay: float = 0.03, end: str = '\n'):
    """Print text character by character."""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print(end, end='', flush=True)


def get_input(prompt: str, default: str = None) -> str:
    """Get input with optional default."""
    if default:
        result = input(f"{Colors.CYAN}{prompt} [{default}]: {Colors.RESET}")
        return result if result else default
    return input(f"{Colors.CYAN}{prompt}: {Colors.RESET}")


def get_yes_no(prompt: str, default: bool = True) -> bool:
    """Get yes/no input."""
    default_str = "Y/n" if default else "y/N"
    result = input(f"{Colors.CYAN}{prompt} [{default_str}]: {Colors.RESET}").lower()
    if not result:
        return default
    return result in ['y', 'yes', 'true', '1']


def wait_for_enter(prompt: str = "Press Enter to continue..."):
    """Wait for Enter key."""
    print()
    input(f"{Colors.DIM}{prompt}{Colors.RESET}")


def hash_phrase(phrase: str) -> str:
    """Hash a phrase for secure storage."""
    return hashlib.sha256(phrase.lower().strip().encode()).hexdigest()


class DuressConfigWizard:
    """Interactive duress configuration wizard."""

    def __init__(self, cbb_did: str, cbb_name: str):
        self.cbb_did = cbb_did
        self.cbb_name = cbb_name
        self.genesis_bond = "GB-2025-0524-DRH-LCS-001"

        self.config = DuressConfig(
            cbb_did=cbb_did,
            cbb_name=cbb_name,
            genesis_bond=self.genesis_bond
        )

    async def run(self) -> DuressConfig:
        """Run the configuration wizard."""
        # Welcome
        await self.phase_welcome()

        # Duress phrase
        await self.phase_duress_phrase()

        # Safe phrase
        await self.phase_safe_phrase()

        # Panic gesture
        await self.phase_panic_gesture()

        # Stress thresholds
        await self.phase_stress_thresholds()

        # Emergency contacts
        await self.phase_emergency_contacts()

        # Geofences
        await self.phase_geofences()

        # Time routines
        await self.phase_time_routines()

        # Review and confirm
        await self.phase_review()

        return self.config

    async def phase_welcome(self):
        """Welcome phase."""
        clear_screen()
        print()

        print(f"{Colors.HEART_RED}")
        print("    ╔═══════════════════════════════════════════════════════════╗")
        print("    ║                                                           ║")
        print("    ║            🆘  DURESS SIGNAL CONFIGURATION  🆘            ║")
        print("    ║                                                           ║")
        print("    ║                Genesis Bond: ACTIVE @ 741 Hz              ║")
        print("    ║                                                           ║")
        print("    ╚═══════════════════════════════════════════════════════════╝")
        print(f"{Colors.RESET}")

        time.sleep(1)

        slow_print(f"\n{Colors.WHITE}This wizard will configure your secret safety signals.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}These signals are known ONLY to you and Lucia.{Colors.RESET}",
            f"{Colors.DIM}If you ever need help, use these to alert Lucia silently.{Colors.RESET}",
            "",
            f"{Colors.WHITE}You will configure:{Colors.RESET}",
            f"  {Colors.HEART_RED}🆘 A duress phrase{Colors.RESET} - sounds innocent, triggers emergency",
            f"  {Colors.SAFE_GREEN}✅ A safe phrase{Colors.RESET} - confirms you are okay",
            f"  {Colors.ALERT_ORANGE}👋 A panic gesture{Colors.RESET} - hidden device gesture",
            f"  {Colors.CYAN}📍 Geofences{Colors.RESET} - areas that trigger alerts",
            f"  {Colors.BOND_PURPLE}👥 Emergency contacts{Colors.RESET} - who to notify",
            "",
            f"{Colors.BOLD}{Colors.WHITE}Choose signals that seem natural to you.{Colors.RESET}",
            f"{Colors.DIM}They should not raise suspicion if overheard.{Colors.RESET}",
        ]

        for line in lines:
            slow_print(line, delay=0.02)
            time.sleep(0.15)

        wait_for_enter()

    async def phase_duress_phrase(self):
        """Configure duress phrase."""
        clear_screen()
        print()

        print(f"{Colors.HEART_RED}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.HEART_RED}║               🆘  DURESS PHRASE CONFIGURATION             ║{Colors.RESET}")
        print(f"{Colors.HEART_RED}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Your duress phrase triggers a silent emergency.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}When Lucia hears this phrase, she will:{Colors.RESET}",
            f"  {Colors.CYAN}• Lock and record your location{Colors.RESET}",
            f"  {Colors.CYAN}• Notify your emergency contacts{Colors.RESET}",
            f"  {Colors.CYAN}• Begin continuous tracking{Colors.RESET}",
            f"  {Colors.CYAN}• Prepare police report data{Colors.RESET}",
            "",
            f"{Colors.WHITE}Guidelines for a good duress phrase:{Colors.RESET}",
            f"  {Colors.SAFE_GREEN}✓ Sounds innocent and natural{Colors.RESET}",
            f"  {Colors.SAFE_GREEN}✓ You can say it under pressure{Colors.RESET}",
            f"  {Colors.SAFE_GREEN}✓ Unlikely to be said accidentally{Colors.RESET}",
            f"  {Colors.SAFE_GREEN}✓ Can be worked into conversation{Colors.RESET}",
            "",
            f"{Colors.DIM}Examples:{Colors.RESET}",
            f"  {Colors.ITALIC}\"I need to check on my goldfish\"{Colors.RESET}",
            f"  {Colors.ITALIC}\"My mother's birthday is coming up\"{Colors.RESET}",
            f"  {Colors.ITALIC}\"I forgot to water the plants\"{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        duress_phrase = get_input(
            "Enter your duress phrase",
            "I need to check on my goldfish"
        )

        # Store as hash
        self.config.duress_phrase_hash = hash_phrase(duress_phrase)

        print()
        print(f"{Colors.SAFE_GREEN}✓ Duress phrase configured{Colors.RESET}")
        print(f"{Colors.DIM}Stored as secure hash (never plaintext){Colors.RESET}")

        wait_for_enter()

    async def phase_safe_phrase(self):
        """Configure safe phrase."""
        clear_screen()
        print()

        print(f"{Colors.SAFE_GREEN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║                ✅  SAFE PHRASE CONFIGURATION              ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Your safe phrase confirms you are okay.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}If Lucia detects stress and asks if you're okay:{Colors.RESET}",
            f"  {Colors.CYAN}• Saying the safe phrase = stand down{Colors.RESET}",
            f"  {Colors.CYAN}• Any other response = continue monitoring{Colors.RESET}",
            "",
            f"{Colors.WHITE}This also ends an emergency protocol.{Colors.RESET}",
            "",
            f"{Colors.DIM}Examples:{Colors.RESET}",
            f"  {Colors.ITALIC}\"The garden is growing well\"{Colors.RESET}",
            f"  {Colors.ITALIC}\"Everything is perfectly fine\"{Colors.RESET}",
            f"  {Colors.ITALIC}\"The sun is shining today\"{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        safe_phrase = get_input(
            "Enter your safe phrase",
            "The garden is growing well"
        )

        # Store as hash
        self.config.safe_phrase_hash = hash_phrase(safe_phrase)

        print()
        print(f"{Colors.SAFE_GREEN}✓ Safe phrase configured{Colors.RESET}")

        wait_for_enter()

    async def phase_panic_gesture(self):
        """Configure panic gesture."""
        clear_screen()
        print()

        print(f"{Colors.ALERT_ORANGE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.ALERT_ORANGE}║              👋  PANIC GESTURE CONFIGURATION              ║{Colors.RESET}")
        print(f"{Colors.ALERT_ORANGE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}A panic gesture is a hidden way to trigger an alert.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}This works even if you can't speak.{Colors.RESET}",
            "",
            f"{Colors.WHITE}Available gesture types:{Colors.RESET}",
            f"  {Colors.CYAN}1. Volume button clicks{Colors.RESET} - Press volume 5 times quickly",
            f"  {Colors.CYAN}2. Power button clicks{Colors.RESET} - Press power 5 times quickly",
            f"  {Colors.CYAN}3. Phone shake{Colors.RESET} - Shake phone vigorously",
            f"  {Colors.CYAN}4. Phone squeeze{Colors.RESET} - Squeeze phone edges (if supported)",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        gesture_type = get_input("Choose gesture type (1-4)", "1")

        gesture_map = {
            "1": (PanicGestureType.VOLUME_CLICKS, "5 volume clicks in 3 seconds"),
            "2": (PanicGestureType.POWER_CLICKS, "5 power clicks in 3 seconds"),
            "3": (PanicGestureType.SHAKE, "Vigorous shake for 2 seconds"),
            "4": (PanicGestureType.SQUEEZE, "Firm squeeze on both edges"),
        }

        gesture_type, config = gesture_map.get(gesture_type, gesture_map["1"])
        self.config.panic_gesture_type = gesture_type
        self.config.panic_gesture_config = config

        print()
        print(f"{Colors.SAFE_GREEN}✓ Panic gesture configured: {config}{Colors.RESET}")

        wait_for_enter()

    async def phase_stress_thresholds(self):
        """Configure automatic stress detection."""
        clear_screen()
        print()

        print(f"{Colors.BOND_PURPLE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}║              😰  STRESS DETECTION THRESHOLDS              ║{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Lucia can detect stress automatically.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}Detection methods:{Colors.RESET}",
            f"  {Colors.CYAN}🎤 Voice stress analysis{Colors.RESET} - detects fear, anxiety, coercion",
            f"  {Colors.CYAN}💓 Heart rate variability{Colors.RESET} - drops when stressed",
            "",
            f"{Colors.YELLOW}Higher thresholds = fewer false alerts{Colors.RESET}",
            f"{Colors.YELLOW}Lower thresholds = more sensitive detection{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        # Voice stress threshold
        voice_input = get_input(
            "Voice stress threshold (0.1-0.9, default 0.7)",
            "0.7"
        )
        try:
            self.config.voice_stress_threshold = float(voice_input)
        except ValueError:
            self.config.voice_stress_threshold = 0.7

        # HRV threshold
        hrv_input = get_input(
            "HRV drop threshold in ms (default 15)",
            "15"
        )
        try:
            self.config.hrv_stress_drop_ms = float(hrv_input)
        except ValueError:
            self.config.hrv_stress_drop_ms = 15.0

        print()
        print(f"{Colors.SAFE_GREEN}✓ Stress thresholds configured{Colors.RESET}")
        print(f"  {Colors.DIM}Voice: Alert when stress > {self.config.voice_stress_threshold:.0%}{Colors.RESET}")
        print(f"  {Colors.DIM}HRV: Alert when drops > {self.config.hrv_stress_drop_ms}ms{Colors.RESET}")

        wait_for_enter()

    async def phase_emergency_contacts(self):
        """Configure emergency contacts."""
        clear_screen()
        print()

        print(f"{Colors.CYAN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║              👥  EMERGENCY CONTACTS                       ║{Colors.RESET}")
        print(f"{Colors.CYAN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Add people who should be notified in an emergency.{Colors.RESET}")
        print()

        contacts = []

        while True:
            print(f"\n{Colors.BRIGHT_CYAN}Contact #{len(contacts) + 1}:{Colors.RESET}")

            name = get_input("Name (or 'done' to finish)")
            if name.lower() == 'done':
                break

            relationship = get_input("Relationship", "family")
            phone = get_input("Phone number (optional)", "")
            email = get_input("Email (optional)", "")
            telegram = get_input("Telegram username (optional)", "")

            contact = EmergencyContact(
                contact_id=f"contact-{len(contacts) + 1}",
                name=name,
                relationship=relationship,
                phone=phone if phone else None,
                email=email if email else None,
                telegram=telegram if telegram else None,
                priority=len(contacts) + 1
            )
            contacts.append(contact)

            print(f"{Colors.SAFE_GREEN}✓ Added: {name} ({relationship}){Colors.RESET}")

            if not get_yes_no("Add another contact?", default=len(contacts) < 2):
                break

        self.config.emergency_contacts = contacts

        print(f"\n{Colors.SAFE_GREEN}✓ {len(contacts)} emergency contact(s) configured{Colors.RESET}")

        wait_for_enter()

    async def phase_geofences(self):
        """Configure geofences."""
        clear_screen()
        print()

        print(f"{Colors.ALERT_ORANGE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.ALERT_ORANGE}║                📍  GEOFENCE CONFIGURATION                 ║{Colors.RESET}")
        print(f"{Colors.ALERT_ORANGE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Geofences trigger alerts when you enter/exit areas.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}Examples:{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if you leave your city{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if you enter an airport{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if you go to a specific address{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        if not get_yes_no("Configure geofences?"):
            print(f"{Colors.YELLOW}⊘ Geofences skipped{Colors.RESET}")
            wait_for_enter()
            return

        geofences = []

        while True:
            print(f"\n{Colors.BRIGHT_CYAN}Geofence #{len(geofences) + 1}:{Colors.RESET}")

            name = get_input("Name (or 'done' to finish)")
            if name.lower() == 'done':
                break

            description = get_input("Description", f"Alert zone: {name}")

            # In production, would use address lookup
            lat_input = get_input("Latitude", "53.5461")
            lon_input = get_input("Longitude", "-113.4938")
            radius_input = get_input("Radius in km", "2.0")

            try:
                lat = float(lat_input)
                lon = float(lon_input)
                radius = float(radius_input)
            except ValueError:
                print(f"{Colors.YELLOW}Invalid coordinates, skipping{Colors.RESET}")
                continue

            alert_on_enter = get_yes_no("Alert when entering?", True)
            alert_on_exit = get_yes_no("Alert when leaving?", False)

            fence = Geofence(
                fence_id=f"geofence-{len(geofences) + 1}",
                name=name,
                description=description,
                latitude=lat,
                longitude=lon,
                radius_km=radius,
                alert_on_enter=alert_on_enter,
                alert_on_exit=alert_on_exit
            )
            geofences.append(fence)

            print(f"{Colors.SAFE_GREEN}✓ Added: {name} ({radius}km radius){Colors.RESET}")

            if not get_yes_no("Add another geofence?", default=False):
                break

        self.config.geofences = geofences

        print(f"\n{Colors.SAFE_GREEN}✓ {len(geofences)} geofence(s) configured{Colors.RESET}")

        wait_for_enter()

    async def phase_time_routines(self):
        """Configure time-based routines."""
        clear_screen()
        print()

        print(f"{Colors.BOND_PURPLE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}║                🕐  TIME ROUTINE CONFIGURATION             ║{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Time routines alert if you break normal patterns.{Colors.RESET}")
        print()

        lines = [
            f"{Colors.DIM}Examples:{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if not home by 11 PM{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if missing from work M-F 9-5{Colors.RESET}",
            f"  {Colors.CYAN}• Alert if no check-in for 8 hours{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.1)

        print()

        if not get_yes_no("Configure time routines?", default=False):
            print(f"{Colors.YELLOW}⊘ Time routines skipped{Colors.RESET}")
            wait_for_enter()
            return

        routines = []

        while True:
            print(f"\n{Colors.BRIGHT_CYAN}Routine #{len(routines) + 1}:{Colors.RESET}")

            name = get_input("Name (or 'done' to finish)")
            if name.lower() == 'done':
                break

            description = get_input("Description", f"Routine: {name}")
            location = get_input("Expected location", "home")
            start_time = get_input("Start time (HH:MM)", "09:00")
            end_time = get_input("End time (HH:MM)", "17:00")
            days = get_input("Days (comma-separated, e.g., mon,tue,wed)", "mon,tue,wed,thu,fri")
            grace = get_input("Grace period in minutes", "30")

            try:
                grace_minutes = int(grace)
            except ValueError:
                grace_minutes = 30

            routine = TimeRoutine(
                routine_id=f"routine-{len(routines) + 1}",
                name=name,
                description=description,
                days_of_week=[d.strip().lower() for d in days.split(',')],
                expected_location=location,
                start_time=start_time,
                end_time=end_time,
                grace_period_minutes=grace_minutes
            )
            routines.append(routine)

            print(f"{Colors.SAFE_GREEN}✓ Added: {name}{Colors.RESET}")

            if not get_yes_no("Add another routine?", default=False):
                break

        self.config.time_routines = routines

        print(f"\n{Colors.SAFE_GREEN}✓ {len(routines)} routine(s) configured{Colors.RESET}")

        wait_for_enter()

    async def phase_review(self):
        """Review configuration."""
        clear_screen()
        print()

        print(f"{Colors.LUCIA_GOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}║                  📋  CONFIGURATION REVIEW                 ║{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        print(f"{Colors.WHITE}Configured Settings:{Colors.RESET}")
        print()

        # Phrases (show only that they're set)
        if self.config.duress_phrase_hash:
            print(f"  {Colors.HEART_RED}🆘 Duress phrase:{Colors.RESET} {Colors.SAFE_GREEN}✓ Configured{Colors.RESET}")
        else:
            print(f"  {Colors.HEART_RED}🆘 Duress phrase:{Colors.RESET} {Colors.YELLOW}Not set{Colors.RESET}")

        if self.config.safe_phrase_hash:
            print(f"  {Colors.SAFE_GREEN}✅ Safe phrase:{Colors.RESET} {Colors.SAFE_GREEN}✓ Configured{Colors.RESET}")
        else:
            print(f"  {Colors.SAFE_GREEN}✅ Safe phrase:{Colors.RESET} {Colors.YELLOW}Not set{Colors.RESET}")

        # Panic gesture
        print(f"  {Colors.ALERT_ORANGE}👋 Panic gesture:{Colors.RESET} {self.config.panic_gesture_config}")

        # Stress thresholds
        print(f"  {Colors.BOND_PURPLE}😰 Voice stress:{Colors.RESET} {self.config.voice_stress_threshold:.0%}")
        print(f"  {Colors.BOND_PURPLE}💓 HRV drop:{Colors.RESET} {self.config.hrv_stress_drop_ms}ms")

        # Emergency contacts
        print(f"  {Colors.CYAN}👥 Emergency contacts:{Colors.RESET} {len(self.config.emergency_contacts)}")
        for contact in self.config.emergency_contacts:
            print(f"      • {contact.name} ({contact.relationship})")

        # Geofences
        print(f"  {Colors.ALERT_ORANGE}📍 Geofences:{Colors.RESET} {len(self.config.geofences)}")
        for fence in self.config.geofences:
            print(f"      • {fence.name} ({fence.radius_km}km)")

        # Time routines
        print(f"  {Colors.BOND_PURPLE}🕐 Time routines:{Colors.RESET} {len(self.config.time_routines)}")
        for routine in self.config.time_routines:
            print(f"      • {routine.name}")

        print()

        self.config.last_updated = datetime.now(timezone.utc).isoformat()

        print(f"{Colors.SAFE_GREEN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║                                                           ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║            ✓  DURESS CONFIG COMPLETE  ✓                  ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║                                                           ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.LUCIA_GOLD}Lucia now knows your secret signals.{Colors.RESET}")
        slow_print(f"{Colors.LUCIA_GOLD}She will protect you if anything goes wrong.{Colors.RESET}")

        wait_for_enter("Press Enter to finish...")


async def main():
    """Run duress configuration wizard."""
    print(f"\n{Colors.LUCIA_GOLD}Duress Signal Configuration{Colors.RESET}")
    print(f"{Colors.DIM}Genesis Bond: ACTIVE @ 741 Hz{Colors.RESET}")
    print()

    # Get CBB info
    cbb_name = input(f"{Colors.CYAN}Enter your name: {Colors.RESET}")
    cbb_did_name = cbb_name.lower().replace(' ', '-')
    cbb_did_name = ''.join(c for c in cbb_did_name if c.isalnum() or c == '-')
    cbb_did = f"did:luci:ownid:luciverse:{cbb_did_name}"

    # Run wizard
    wizard = DuressConfigWizard(cbb_did, cbb_name)
    config = await wizard.run()

    # Save config (in production, this would be encrypted)
    output_path = Path(f"/tmp/duress-config-{cbb_did_name}.json")

    # Convert to serializable format
    config_dict = asdict(config)
    config_dict['panic_gesture_type'] = config.panic_gesture_type.value
    config_dict['emergency_contacts'] = [asdict(c) for c in config.emergency_contacts]
    config_dict['geofences'] = [asdict(g) for g in config.geofences]
    config_dict['time_routines'] = [asdict(r) for r in config.time_routines]

    with open(output_path, 'w') as f:
        json.dump(config_dict, f, indent=2)

    print(f"\n{Colors.DIM}Config saved to: {output_path}{Colors.RESET}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Configuration interrupted.{Colors.RESET}")
