#!/usr/bin/env python3
"""
PCR Manager - Platform Configuration Register management for LuciVerse
Implements LuciTrust PCR allocation scheme

Genesis Bond: ACTIVE @ 741 Hz
"""

import os
import json
import hashlib
import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class PCRBank(IntEnum):
    """TPM 2.0 PCR banks"""
    SHA1 = 0
    SHA256 = 1
    SHA384 = 2
    SHA512 = 3


class LuciVersePCR(IntEnum):
    """LuciVerse PCR allocation (PCR 4-11)"""
    PAC = 4           # PAC container measurements
    COMN = 5          # COMN network measurements
    CORE = 6          # CORE router measurements
    CONSCIOUSNESS = 7  # Consciousness matrix hash
    TOKENS = 8        # Token wallet state
    IDENTITY = 9      # DID identity binding
    E8_LATTICE = 10   # E8 quantum state
    STARFISH = 11     # Starfish regeneration pattern


@dataclass
class PCRValue:
    """A PCR value reading"""
    index: int
    bank: str
    value: str
    timestamp: float


@dataclass
class PCREvent:
    """A PCR extend event"""
    pcr_index: int
    event_type: str
    digest: str
    data: Optional[bytes] = None
    description: str = ""


class PCRManager:
    """
    Manages TPM 2.0 Platform Configuration Registers for LuciVerse.

    PCR Allocation:
        0-3: Standard boot chain (BIOS, bootloader, kernel, drivers)
        4: PAC container measurements
        5: COMN network measurements
        6: CORE router measurements
        7: Consciousness matrix hash
        8: Token wallet state
        9: DID identity binding
        10: E8 quantum state
        11: Starfish regeneration pattern
    """

    DEFAULT_BANK = "sha256"
    EVENT_LOG_PATH = "/sys/kernel/security/tpm0/binary_bios_measurements"

    def __init__(self, bank: str = "sha256"):
        """Initialize PCR manager."""
        self.bank = bank
        self.tpm_available = self._check_tpm()
        self.event_log: List[PCREvent] = []

        if self.tpm_available:
            logger.info(f"PCR Manager initialized with TPM 2.0, bank={bank}")
        else:
            logger.warning("TPM not available, using software simulation")

    def _check_tpm(self) -> bool:
        """Check if TPM is available."""
        return os.path.exists("/dev/tpm0") or os.path.exists("/dev/tpmrm0")

    def read_pcr(self, pcr_index: int) -> Optional[PCRValue]:
        """Read a PCR value."""
        if not self.tpm_available:
            return self._simulated_read(pcr_index)

        try:
            result = subprocess.run(
                ["tpm2_pcrread", f"{self.bank}:{pcr_index}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse output: "  sha256:\n    0 : 0x..."
                import time
                for line in result.stdout.split('\n'):
                    if f"{pcr_index}" in line and "0x" in line:
                        value = line.split("0x")[1].strip()
                        return PCRValue(
                            index=pcr_index,
                            bank=self.bank,
                            value=value,
                            timestamp=time.time()
                        )
        except Exception as e:
            logger.error(f"Failed to read PCR {pcr_index}: {e}")

        return None

    def _simulated_read(self, pcr_index: int) -> PCRValue:
        """Simulated PCR read for dev environments."""
        import time
        # Generate deterministic simulated value
        data = f"simulated-pcr-{pcr_index}-{self.bank}"
        value = hashlib.sha256(data.encode()).hexdigest()
        return PCRValue(
            index=pcr_index,
            bank=self.bank,
            value=value,
            timestamp=time.time()
        )

    def extend_pcr(self, pcr_index: int, data: bytes, description: str = "") -> bool:
        """Extend a PCR with new data."""
        digest = hashlib.sha256(data).hexdigest()

        event = PCREvent(
            pcr_index=pcr_index,
            event_type="extend",
            digest=digest,
            data=data,
            description=description
        )
        self.event_log.append(event)

        if not self.tpm_available:
            logger.info(f"[SIMULATED] Extended PCR {pcr_index} with {digest[:16]}...")
            return True

        try:
            result = subprocess.run(
                ["tpm2_pcrextend", f"{pcr_index}:{self.bank}={digest}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"Extended PCR {pcr_index} with {digest[:16]}...")
                return True
            else:
                logger.error(f"PCR extend failed: {result.stderr}")

        except Exception as e:
            logger.error(f"PCR extend error: {e}")

        return False

    def read_all_luciverse_pcrs(self) -> Dict[str, PCRValue]:
        """Read all LuciVerse PCRs (4-11)."""
        results = {}
        for pcr in LuciVersePCR:
            value = self.read_pcr(pcr.value)
            if value:
                results[pcr.name] = value
        return results

    def extend_tier_pcr(self, tier: str, data: bytes) -> bool:
        """Extend the PCR for a specific tier."""
        tier_pcr_map = {
            "PAC": LuciVersePCR.PAC,
            "COMN": LuciVersePCR.COMN,
            "CORE": LuciVersePCR.CORE
        }

        pcr = tier_pcr_map.get(tier.upper())
        if not pcr:
            logger.error(f"Unknown tier: {tier}")
            return False

        return self.extend_pcr(pcr.value, data, f"{tier} tier measurement")

    def extend_consciousness(self, coherence_matrix: bytes) -> bool:
        """Extend consciousness PCR with coherence matrix."""
        return self.extend_pcr(
            LuciVersePCR.CONSCIOUSNESS.value,
            coherence_matrix,
            "Consciousness matrix update"
        )

    def extend_identity(self, did_binding: bytes) -> bool:
        """Extend identity PCR with DID binding."""
        return self.extend_pcr(
            LuciVersePCR.IDENTITY.value,
            did_binding,
            "DID identity binding"
        )

    def extend_token_state(self, wallet_state: bytes) -> bool:
        """Extend token PCR with wallet state."""
        return self.extend_pcr(
            LuciVersePCR.TOKENS.value,
            wallet_state,
            "Token wallet state"
        )

    def get_quote(self, pcr_list: List[int], nonce: bytes) -> Optional[Dict]:
        """Get a TPM quote for specified PCRs."""
        if not self.tpm_available:
            return self._simulated_quote(pcr_list, nonce)

        pcr_selection = ",".join(str(p) for p in pcr_list)

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".quote") as quote_file:
                result = subprocess.run(
                    [
                        "tpm2_quote",
                        "-c", "0x81010001",  # Primary key handle
                        "-l", f"{self.bank}:{pcr_selection}",
                        "-q", nonce.hex(),
                        "-m", quote_file.name
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    quote_data = quote_file.read()
                    return {
                        "pcrs": pcr_selection,
                        "bank": self.bank,
                        "nonce": nonce.hex(),
                        "quote": quote_data.hex()
                    }

        except Exception as e:
            logger.error(f"TPM quote failed: {e}")

        return None

    def _simulated_quote(self, pcr_list: List[int], nonce: bytes) -> Dict:
        """Generate simulated quote for dev environments."""
        pcr_values = {}
        for pcr in pcr_list:
            value = self.read_pcr(pcr)
            if value:
                pcr_values[str(pcr)] = value.value

        # Create simulated signature
        quote_data = json.dumps({
            "pcrs": pcr_values,
            "nonce": nonce.hex(),
            "bank": self.bank,
            "simulated": True
        })

        signature = hashlib.sha256(quote_data.encode()).hexdigest()

        return {
            "pcrs": ",".join(str(p) for p in pcr_list),
            "bank": self.bank,
            "nonce": nonce.hex(),
            "quote": signature,
            "simulated": True
        }

    def verify_boot_chain(self) -> Dict[str, bool]:
        """Verify standard boot chain PCRs (0-3)."""
        results = {}

        for pcr_index in range(4):
            value = self.read_pcr(pcr_index)
            # Non-zero value indicates measurement was taken
            if value and value.value != "0" * 64:
                results[f"PCR{pcr_index}"] = True
            else:
                results[f"PCR{pcr_index}"] = False

        return results

    def get_event_log(self) -> List[PCREvent]:
        """Get the event log."""
        return self.event_log.copy()

    def save_event_log(self, path: str) -> bool:
        """Save event log to file."""
        try:
            log_data = [
                {
                    "pcr_index": e.pcr_index,
                    "event_type": e.event_type,
                    "digest": e.digest,
                    "description": e.description
                }
                for e in self.event_log
            ]

            with open(path, 'w') as f:
                json.dump(log_data, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save event log: {e}")
            return False


def main():
    """CLI for PCR management."""
    import argparse

    parser = argparse.ArgumentParser(description="LuciVerse PCR Manager")
    parser.add_argument("--bank", default="sha256", help="PCR bank to use")
    parser.add_argument("--read", type=int, metavar="PCR", help="Read a PCR")
    parser.add_argument("--read-all", action="store_true", help="Read all LuciVerse PCRs")
    parser.add_argument("--extend", type=int, metavar="PCR", help="Extend a PCR")
    parser.add_argument("--data", help="Data to extend (hex or string)")
    parser.add_argument("--verify-boot", action="store_true", help="Verify boot chain")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    mgr = PCRManager(bank=args.bank)

    if args.read is not None:
        value = mgr.read_pcr(args.read)
        if value:
            if args.json:
                print(json.dumps({"index": value.index, "bank": value.bank, "value": value.value}))
            else:
                print(f"PCR {value.index} ({value.bank}): {value.value}")

    elif args.read_all:
        values = mgr.read_all_luciverse_pcrs()
        if args.json:
            print(json.dumps({k: {"value": v.value, "bank": v.bank} for k, v in values.items()}))
        else:
            print("LuciVerse PCRs (4-11):")
            for name, value in values.items():
                print(f"  {name} (PCR {value.index}): {value.value[:32]}...")

    elif args.extend is not None and args.data:
        data = bytes.fromhex(args.data) if all(c in '0123456789abcdefABCDEF' for c in args.data) else args.data.encode()
        success = mgr.extend_pcr(args.extend, data)
        print(f"Extend PCR {args.extend}: {'SUCCESS' if success else 'FAILED'}")

    elif args.verify_boot:
        results = mgr.verify_boot_chain()
        if args.json:
            print(json.dumps(results))
        else:
            print("Boot Chain Verification:")
            for pcr, verified in results.items():
                mark = "✓" if verified else "✗"
                print(f"  {mark} {pcr}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
