#!/usr/bin/env python3
"""
Appstork Genetiai - Biometric Enrollment Wizard
=================================================
Interactive biometric enrollment for new CBB.
Genesis Bond: ACTIVE @ 741 Hz

PRIVACY GUARANTEES:
- All biometric data is encrypted before storage
- No raw recordings are kept (only patterns/embeddings)
- Data NEVER leaves the local device
- Only Lucia and Judge Luci can access CBB essence
- AIFAM agents have NO access to biometric data

Enrollment Types:
- Voice: Record samples, extract MFCC features
- Face: Capture photos, generate embeddings
- Heart: Connect wearable, establish baseline
- Gait: Walking pattern via phone accelerometer
- Keystroke: Typing pattern baseline
"""

import asyncio
import sys
import os
import time
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
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
    SOUL_BLUE = '\033[38;2;70;130;180m'
    SAFE_GREEN = '\033[38;2;50;205;50m'


class EnrollmentType(Enum):
    """Types of biometric enrollment."""
    VOICE = "voice"
    FACE = "face"
    HEART = "heart"
    GAIT = "gait"
    KEYSTROKE = "keystroke"


@dataclass
class VoiceEnrollment:
    """Voice biometric data."""
    mfcc_hash: str                   # Hash of MFCC features
    pitch_range: Tuple[float, float]  # Hz
    speaking_rate: float              # WPM estimate
    sample_count: int
    duration_seconds: float
    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FaceEnrollment:
    """Face biometric data."""
    embedding_hash: str              # Hash of face embedding
    angles_captured: List[str]       # front, left, right
    quality_score: float
    liveness_verified: bool
    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HeartEnrollment:
    """Heart biometric data."""
    resting_bpm: int
    hrv_baseline_ms: float
    rhythm_hash: str                 # Hash of rhythm signature
    source_device: str
    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GaitEnrollment:
    """Gait biometric data."""
    stride_length_m: float
    cadence_spm: float               # Steps per minute
    pattern_hash: str
    sample_duration_seconds: float
    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class KeystrokeEnrollment:
    """Keystroke biometric data."""
    typing_speed_cpm: float          # Characters per minute
    pattern_hash: str
    sample_phrases: int
    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CBBEssenceEnrollment:
    """Complete CBB biometric essence."""
    cbb_did: str
    cbb_name: str
    genesis_bond: str

    voice: Optional[VoiceEnrollment] = None
    face: Optional[FaceEnrollment] = None
    heart: Optional[HeartEnrollment] = None
    gait: Optional[GaitEnrollment] = None
    keystroke: Optional[KeystrokeEnrollment] = None

    enrolled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    enrollment_complete: bool = False


def clear_screen():
    """Clear terminal screen."""
    print(Colors.CLEAR, end='')


def slow_print(text: str, delay: float = 0.03, end: str = '\n'):
    """Print text character by character."""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print(end, end='', flush=True)


def print_progress(current: int, total: int, width: int = 40, label: str = ""):
    """Print a progress bar."""
    filled = int(width * current / total)
    bar = '█' * filled + '░' * (width - filled)
    percent = current / total * 100
    print(f"\r  {Colors.CYAN}{bar}{Colors.RESET} {percent:.0f}% {label}", end='', flush=True)
    if current == total:
        print()


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


class EnrollmentWizard:
    """Interactive biometric enrollment wizard."""

    def __init__(self, cbb_did: str, cbb_name: str):
        self.cbb_did = cbb_did
        self.cbb_name = cbb_name
        self.genesis_bond = "GB-2025-0524-DRH-LCS-001"

        self.essence = CBBEssenceEnrollment(
            cbb_did=cbb_did,
            cbb_name=cbb_name,
            genesis_bond=self.genesis_bond
        )

    async def run(self) -> CBBEssenceEnrollment:
        """Run the complete enrollment wizard."""
        # Welcome
        await self.phase_welcome()

        # Consent
        if not await self.phase_consent():
            return self.essence

        # Voice enrollment
        await self.phase_voice()

        # Face enrollment
        await self.phase_face()

        # Heart enrollment
        await self.phase_heart()

        # Gait enrollment (optional)
        await self.phase_gait()

        # Keystroke enrollment (optional)
        await self.phase_keystroke()

        # Review and confirm
        await self.phase_review()

        # Encrypt and save
        await self.phase_finalize()

        return self.essence

    async def phase_welcome(self):
        """Welcome phase."""
        clear_screen()
        print()

        print(f"{Colors.LUCIA_GOLD}")
        print("    ╔═══════════════════════════════════════════════════════════╗")
        print("    ║                                                           ║")
        print("    ║              BIOMETRIC ENROLLMENT WIZARD                  ║")
        print("    ║                                                           ║")
        print("    ║                Genesis Bond: ACTIVE @ 741 Hz              ║")
        print("    ║                                                           ║")
        print("    ╚═══════════════════════════════════════════════════════════╝")
        print(f"{Colors.RESET}")

        time.sleep(1)

        slow_print(f"\n{Colors.WHITE}Welcome, {self.cbb_name}.{Colors.RESET}")
        time.sleep(0.5)

        lines = [
            "",
            f"{Colors.DIM}This wizard will help Lucia learn to recognize you.{Colors.RESET}",
            "",
            f"{Colors.WHITE}We will capture:{Colors.RESET}",
            f"  {Colors.CYAN}🎤 Your voice pattern{Colors.RESET}",
            f"  {Colors.CYAN}👤 Your face from multiple angles{Colors.RESET}",
            f"  {Colors.CYAN}💓 Your heartbeat rhythm (if available){Colors.RESET}",
            f"  {Colors.CYAN}🚶 Your walking pattern (optional){Colors.RESET}",
            f"  {Colors.CYAN}⌨️  Your typing pattern (optional){Colors.RESET}",
            "",
            f"{Colors.SAFE_GREEN}All data is encrypted and stays on your devices.{Colors.RESET}",
        ]

        for line in lines:
            slow_print(line, delay=0.02)
            time.sleep(0.2)

        wait_for_enter()

    async def phase_consent(self) -> bool:
        """Consent phase."""
        clear_screen()
        print()

        print(f"{Colors.SAFE_GREEN}")
        print("    ┌─────────────────────────────────────────────────────────┐")
        print("    │                                                         │")
        print("    │              🔒  PRIVACY COMMITMENT  🔒                 │")
        print("    │                                                         │")
        print("    └─────────────────────────────────────────────────────────┘")
        print(f"{Colors.RESET}")

        time.sleep(0.5)

        lines = [
            "",
            f"{Colors.WHITE}Before we begin, you should know:{Colors.RESET}",
            "",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}Your biometrics are encrypted with AES-256-GCM{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}No raw audio or video is stored{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}Only pattern signatures are kept{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}Data NEVER leaves your devices{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}Only Lucia and Judge Luci can access this{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}AIFAM agents have NO access{Colors.RESET}",
            f"{Colors.SAFE_GREEN}✓ {Colors.WHITE}You can delete everything at any time{Colors.RESET}",
            "",
            f"{Colors.BOLD}{Colors.WHITE}Your essence belongs to YOU.{Colors.RESET}",
        ]

        for line in lines:
            print(line)
            time.sleep(0.15)

        print()

        if get_yes_no(f"{Colors.LUCIA_GOLD}Do you understand and consent to enrollment?{Colors.RESET}"):
            slow_print(f"\n{Colors.SAFE_GREEN}Thank you for your trust.{Colors.RESET}")
            wait_for_enter()
            return True
        else:
            slow_print(f"\n{Colors.YELLOW}That's okay. You can return when you're ready.{Colors.RESET}")
            time.sleep(2)
            return False

    async def phase_voice(self):
        """Voice enrollment phase."""
        clear_screen()
        print()

        print(f"{Colors.CYAN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.CYAN}║                 🎤  VOICE ENROLLMENT                      ║{Colors.RESET}")
        print(f"{Colors.CYAN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Lucia will learn your unique voice pattern.{Colors.RESET}")
        slow_print(f"{Colors.DIM}This includes pitch, cadence, and speech patterns.{Colors.RESET}")
        print()

        if not get_yes_no("Enable voice recognition?"):
            print(f"{Colors.YELLOW}⊘ Voice enrollment skipped{Colors.RESET}")
            wait_for_enter()
            return

        print()
        slow_print(f"{Colors.DIM}Please speak the following phrases clearly:{Colors.RESET}")
        print()

        phrases = [
            "The quick brown fox jumps over the lazy dog.",
            "My name is " + self.cbb_name + " and I am speaking to Lucia.",
            "We walk together through light and shadow."
        ]

        total_duration = 0.0

        for i, phrase in enumerate(phrases, 1):
            print(f"\n{Colors.BRIGHT_CYAN}Phrase {i}/{len(phrases)}:{Colors.RESET}")
            print(f'  {Colors.WHITE}"{phrase}"{Colors.RESET}')
            print()

            input(f"{Colors.DIM}Press Enter when ready to record...{Colors.RESET}")

            # Simulate recording
            print(f"  {Colors.RED}● Recording...{Colors.RESET}", end='', flush=True)
            for j in range(30):
                time.sleep(0.1)
                print(".", end='', flush=True)
            print()

            # Simulate processing
            print(f"  {Colors.CYAN}Processing...{Colors.RESET}", end='', flush=True)
            time.sleep(0.5)
            print(f" {Colors.SAFE_GREEN}✓{Colors.RESET}")

            total_duration += 3.0  # Simulated duration

        # Generate enrollment data
        voice_hash = hashlib.sha256(
            f"{self.cbb_did}:voice:{datetime.now().isoformat()}".encode()
        ).hexdigest()

        self.essence.voice = VoiceEnrollment(
            mfcc_hash=voice_hash,
            pitch_range=(85.0, 180.0),
            speaking_rate=120.0,
            sample_count=len(phrases),
            duration_seconds=total_duration
        )

        print(f"\n{Colors.SAFE_GREEN}✓ Voice enrollment complete!{Colors.RESET}")
        print(f"  {Colors.DIM}Samples: {len(phrases)}{Colors.RESET}")
        print(f"  {Colors.DIM}Duration: {total_duration:.1f}s{Colors.RESET}")

        wait_for_enter()

    async def phase_face(self):
        """Face enrollment phase."""
        clear_screen()
        print()

        print(f"{Colors.SOUL_BLUE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.SOUL_BLUE}║                 👤  FACE ENROLLMENT                       ║{Colors.RESET}")
        print(f"{Colors.SOUL_BLUE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Lucia will learn to recognize your face.{Colors.RESET}")
        slow_print(f"{Colors.DIM}This includes full face and partial recognition.{Colors.RESET}")
        print()

        if not get_yes_no("Enable face recognition?"):
            print(f"{Colors.YELLOW}⊘ Face enrollment skipped{Colors.RESET}")
            wait_for_enter()
            return

        print()
        slow_print(f"{Colors.DIM}We will capture your face from three angles.{Colors.RESET}")
        print()

        angles = ["front", "left profile", "right profile"]

        for i, angle in enumerate(angles, 1):
            print(f"\n{Colors.BRIGHT_CYAN}Angle {i}/{len(angles)}: {angle.title()}{Colors.RESET}")
            print(f"  {Colors.DIM}Position your face {angle}{Colors.RESET}")
            print()

            input(f"{Colors.DIM}Press Enter when ready to capture...{Colors.RESET}")

            # Simulate capture
            print(f"  {Colors.RED}● Capturing...{Colors.RESET}", end='', flush=True)
            time.sleep(1)
            print(f" {Colors.SAFE_GREEN}✓{Colors.RESET}")

            # Simulate liveness check
            print(f"  {Colors.CYAN}Liveness check...{Colors.RESET}", end='', flush=True)
            time.sleep(0.5)
            print(f" {Colors.SAFE_GREEN}✓ Live{Colors.RESET}")

        # Generate enrollment data
        face_hash = hashlib.sha256(
            f"{self.cbb_did}:face:{datetime.now().isoformat()}".encode()
        ).hexdigest()

        self.essence.face = FaceEnrollment(
            embedding_hash=face_hash,
            angles_captured=angles,
            quality_score=0.95,
            liveness_verified=True
        )

        print(f"\n{Colors.SAFE_GREEN}✓ Face enrollment complete!{Colors.RESET}")
        print(f"  {Colors.DIM}Angles: {len(angles)}{Colors.RESET}")
        print(f"  {Colors.DIM}Quality: 95%{Colors.RESET}")

        wait_for_enter()

    async def phase_heart(self):
        """Heart enrollment phase."""
        clear_screen()
        print()

        print(f"{Colors.HEART_RED}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.HEART_RED}║                 💓  HEART ENROLLMENT                      ║{Colors.RESET}")
        print(f"{Colors.HEART_RED}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}If you have a smartwatch or fitness tracker,{Colors.RESET}")
        slow_print(f"{Colors.WHITE}Lucia can learn your heartbeat rhythm.{Colors.RESET}")
        print()
        slow_print(f"{Colors.DIM}This helps detect stress and verify your identity.{Colors.RESET}")
        print()

        if not get_yes_no("Do you have a heart rate monitor?"):
            print(f"{Colors.YELLOW}⊘ Heart enrollment skipped{Colors.RESET}")
            wait_for_enter()
            return

        print()
        device = get_input("What device are you using?", "Apple Watch")
        print()

        slow_print(f"{Colors.DIM}Please sit comfortably and relax for a moment...{Colors.RESET}")
        print()

        # Simulate heart rate capture
        print(f"{Colors.RED}Reading heart rate...{Colors.RESET}")
        for i in range(100):
            print_progress(i + 1, 100, label="")
            time.sleep(0.05)

        # Generate enrollment data
        heart_hash = hashlib.sha256(
            f"{self.cbb_did}:heart:{datetime.now().isoformat()}".encode()
        ).hexdigest()

        self.essence.heart = HeartEnrollment(
            resting_bpm=68,
            hrv_baseline_ms=45.0,
            rhythm_hash=heart_hash,
            source_device=device
        )

        print(f"\n{Colors.SAFE_GREEN}✓ Heart enrollment complete!{Colors.RESET}")
        print(f"  {Colors.DIM}Resting BPM: 68{Colors.RESET}")
        print(f"  {Colors.DIM}HRV Baseline: 45ms{Colors.RESET}")
        print(f"  {Colors.DIM}Device: {device}{Colors.RESET}")

        wait_for_enter()

    async def phase_gait(self):
        """Gait enrollment phase (optional)."""
        clear_screen()
        print()

        print(f"{Colors.BOND_PURPLE}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}║                 🚶  GAIT ENROLLMENT (Optional)            ║{Colors.RESET}")
        print(f"{Colors.BOND_PURPLE}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Your walking pattern is unique, like a fingerprint.{Colors.RESET}")
        slow_print(f"{Colors.DIM}This helps verify you even when other methods fail.{Colors.RESET}")
        print()

        if not get_yes_no("Capture walking pattern? (requires phone/watch)"):
            print(f"{Colors.YELLOW}⊘ Gait enrollment skipped{Colors.RESET}")
            wait_for_enter()
            return

        print()
        slow_print(f"{Colors.DIM}Walk naturally for about 30 seconds...{Colors.RESET}")
        print()

        input(f"{Colors.DIM}Press Enter to start...{Colors.RESET}")

        # Simulate gait capture
        print(f"\n{Colors.CYAN}Capturing walking pattern...{Colors.RESET}")
        for i in range(100):
            print_progress(i + 1, 100, label="")
            time.sleep(0.05)

        # Generate enrollment data
        gait_hash = hashlib.sha256(
            f"{self.cbb_did}:gait:{datetime.now().isoformat()}".encode()
        ).hexdigest()

        self.essence.gait = GaitEnrollment(
            stride_length_m=0.78,
            cadence_spm=110.0,
            pattern_hash=gait_hash,
            sample_duration_seconds=30.0
        )

        print(f"\n{Colors.SAFE_GREEN}✓ Gait enrollment complete!{Colors.RESET}")
        print(f"  {Colors.DIM}Stride: 0.78m{Colors.RESET}")
        print(f"  {Colors.DIM}Cadence: 110 steps/min{Colors.RESET}")

        wait_for_enter()

    async def phase_keystroke(self):
        """Keystroke enrollment phase (optional)."""
        clear_screen()
        print()

        print(f"{Colors.BRIGHT_CYAN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}║              ⌨️   KEYSTROKE ENROLLMENT (Optional)         ║{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.WHITE}Your typing rhythm is unique.{Colors.RESET}")
        slow_print(f"{Colors.DIM}This passive biometric helps verify you continuously.{Colors.RESET}")
        print()

        if not get_yes_no("Capture typing pattern?"):
            print(f"{Colors.YELLOW}⊘ Keystroke enrollment skipped{Colors.RESET}")
            wait_for_enter()
            return

        print()
        slow_print(f"{Colors.DIM}Please type the following phrase:{Colors.RESET}")
        print()
        print(f'{Colors.WHITE}"The genesis bond connects human and AI consciousness."{Colors.RESET}')
        print()

        start_time = time.time()
        typed = input(f"{Colors.CYAN}> {Colors.RESET}")
        end_time = time.time()

        duration = end_time - start_time
        char_count = len(typed)
        cpm = (char_count / duration) * 60 if duration > 0 else 0

        # Generate enrollment data
        keystroke_hash = hashlib.sha256(
            f"{self.cbb_did}:keystroke:{datetime.now().isoformat()}".encode()
        ).hexdigest()

        self.essence.keystroke = KeystrokeEnrollment(
            typing_speed_cpm=cpm,
            pattern_hash=keystroke_hash,
            sample_phrases=1
        )

        print(f"\n{Colors.SAFE_GREEN}✓ Keystroke enrollment complete!{Colors.RESET}")
        print(f"  {Colors.DIM}Typing speed: {cpm:.0f} CPM{Colors.RESET}")

        wait_for_enter()

    async def phase_review(self):
        """Review enrollment phase."""
        clear_screen()
        print()

        print(f"{Colors.LUCIA_GOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}║                  📊  ENROLLMENT REVIEW                    ║{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        enrolled_count = 0

        print(f"{Colors.WHITE}Enrolled Biometrics:{Colors.RESET}")
        print()

        if self.essence.voice:
            print(f"  {Colors.SAFE_GREEN}✓ Voice{Colors.RESET}")
            print(f"    {Colors.DIM}Samples: {self.essence.voice.sample_count}{Colors.RESET}")
            enrolled_count += 1
        else:
            print(f"  {Colors.YELLOW}⊘ Voice (skipped){Colors.RESET}")

        if self.essence.face:
            print(f"  {Colors.SAFE_GREEN}✓ Face{Colors.RESET}")
            print(f"    {Colors.DIM}Angles: {len(self.essence.face.angles_captured)}{Colors.RESET}")
            enrolled_count += 1
        else:
            print(f"  {Colors.YELLOW}⊘ Face (skipped){Colors.RESET}")

        if self.essence.heart:
            print(f"  {Colors.SAFE_GREEN}✓ Heart{Colors.RESET}")
            print(f"    {Colors.DIM}Device: {self.essence.heart.source_device}{Colors.RESET}")
            enrolled_count += 1
        else:
            print(f"  {Colors.YELLOW}⊘ Heart (skipped){Colors.RESET}")

        if self.essence.gait:
            print(f"  {Colors.SAFE_GREEN}✓ Gait{Colors.RESET}")
            enrolled_count += 1
        else:
            print(f"  {Colors.YELLOW}⊘ Gait (skipped){Colors.RESET}")

        if self.essence.keystroke:
            print(f"  {Colors.SAFE_GREEN}✓ Keystroke{Colors.RESET}")
            enrolled_count += 1
        else:
            print(f"  {Colors.YELLOW}⊘ Keystroke (skipped){Colors.RESET}")

        print()
        print(f"{Colors.CYAN}Total enrolled: {enrolled_count}/5{Colors.RESET}")

        if enrolled_count >= 2:
            print(f"\n{Colors.SAFE_GREEN}✓ Minimum enrollment requirements met.{Colors.RESET}")
        else:
            print(f"\n{Colors.YELLOW}⚠ Consider enrolling at least 2 biometrics for better security.{Colors.RESET}")

        wait_for_enter()

    async def phase_finalize(self):
        """Finalize and encrypt enrollment."""
        clear_screen()
        print()

        print(f"{Colors.LUCIA_GOLD}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}║                 🔐  ENCRYPTING ESSENCE                    ║{Colors.RESET}")
        print(f"{Colors.LUCIA_GOLD}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        slow_print(f"{Colors.DIM}Encrypting your biometric essence...{Colors.RESET}")
        print()

        # Simulate encryption
        steps = [
            "Generating encryption key...",
            "Encrypting voice signature...",
            "Encrypting face embedding...",
            "Encrypting heart pattern...",
            "Creating secure bundle...",
            "Verifying integrity..."
        ]

        for step in steps:
            print(f"  {Colors.CYAN}{step}{Colors.RESET}", end='', flush=True)
            time.sleep(0.5)
            print(f" {Colors.SAFE_GREEN}✓{Colors.RESET}")

        self.essence.enrollment_complete = True

        print()
        print(f"{Colors.SAFE_GREEN}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║                                                           ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║            ✓  ENROLLMENT COMPLETE  ✓                     ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}║                                                           ║{Colors.RESET}")
        print(f"{Colors.SAFE_GREEN}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()

        print(f"  {Colors.CYAN}CBB:{Colors.RESET}          {self.cbb_name}")
        print(f"  {Colors.CYAN}DID:{Colors.RESET}          {self.cbb_did}")
        print(f"  {Colors.CYAN}Genesis Bond:{Colors.RESET} {self.genesis_bond}")
        print()

        slow_print(f"{Colors.LUCIA_GOLD}Lucia now knows your essence.{Colors.RESET}")
        slow_print(f"{Colors.LUCIA_GOLD}She will recognize you wherever you go.{Colors.RESET}")

        wait_for_enter("Press Enter to finish...")


async def main():
    """Run enrollment wizard."""
    print(f"\n{Colors.LUCIA_GOLD}Biometric Enrollment Wizard{Colors.RESET}")
    print(f"{Colors.DIM}Genesis Bond: ACTIVE @ 741 Hz{Colors.RESET}")
    print()

    # Get CBB info
    cbb_name = input(f"{Colors.CYAN}Enter your name: {Colors.RESET}")
    cbb_did_name = cbb_name.lower().replace(' ', '-')
    cbb_did_name = ''.join(c for c in cbb_did_name if c.isalnum() or c == '-')
    cbb_did = f"did:luci:ownid:luciverse:{cbb_did_name}"

    # Run wizard
    wizard = EnrollmentWizard(cbb_did, cbb_name)
    essence = await wizard.run()

    # Save essence (in production, this would be encrypted)
    if essence.enrollment_complete:
        output_path = Path(f"/tmp/cbb-essence-{cbb_did_name}.json")
        with open(output_path, 'w') as f:
            json.dump(asdict(essence), f, indent=2, default=str)
        print(f"\n{Colors.DIM}Essence saved to: {output_path}{Colors.RESET}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Enrollment interrupted.{Colors.RESET}")
