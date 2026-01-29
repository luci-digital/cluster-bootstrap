# SCION Header Parser for LuciVerse
# Genesis Bond: GB-2025-0524-DRH-LCS-001
#
# Implements SCION packet header parsing per:
# https://scionassociation.github.io/scion-dp_I-D/draft-dekater-scion-dataplane.html
#
# SCION Packet Structure:
# ┌────────────────────────┐
# │    Common Header       │ 12 bytes
# ├────────────────────────┤
# │    Address Header      │ Variable (16-48 bytes)
# ├────────────────────────┤
# │    Path Header         │ Variable
# ├────────────────────────┤
# │  Extension Headers     │ Optional (HBH/E2E)
# ├────────────────────────┤
# │    Upper Layer         │ UDP/SCMP/etc.
# └────────────────────────┘

import struct
import hashlib
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple


class NextHeader(IntEnum):
    """SCION Next Header values (Section 3.1)."""
    HOP_BY_HOP = 200
    END_TO_END = 201
    SCMP = 202
    BFD = 203
    UDP = 17
    NONE = 59


class PathType(IntEnum):
    """SCION Path Types (Section 4)."""
    EMPTY = 0       # Intra-AS communication
    SCION = 1       # Standard SCION path
    ONEHOP = 2      # One-hop bootstrap path
    EPIC = 3        # EPIC authenticated path
    COLIBRI = 4     # QoS reservation path


class AddrType(IntEnum):
    """Address types (Section 3.2)."""
    IPV4 = 0
    IPV6 = 1
    SERVICE = 2


@dataclass
class CommonHeader:
    """
    SCION Common Header (12 bytes, Section 3.1).

    Format (4-byte aligned):
    ┌─────────┬─────────┬─────────┬─────────┐
    │ Version │ TrafficClass     │ FlowID  │  4 bytes
    ├─────────┼─────────┴─────────┼─────────┤
    │ NextHdr │ HdrLen  │ PayLen  │ PthType │  4 bytes
    ├─────────┼─────────┼─────────┼─────────┤
    │ DT │ DL│ ST │ SL│ Reserved         │  4 bytes
    └─────────┴─────────┴─────────┴─────────┘
    """
    version: int = 0              # 4 bits, must be 0
    traffic_class: int = 0        # 8 bits
    flow_id: int = 0              # 20 bits
    next_header: NextHeader = NextHeader.UDP
    header_length: int = 0        # In 4-byte units
    payload_length: int = 0       # In bytes
    path_type: PathType = PathType.SCION
    dst_addr_type: AddrType = AddrType.IPV4
    dst_addr_len: int = 0         # (DL+1)*4 bytes
    src_addr_type: AddrType = AddrType.IPV4
    src_addr_len: int = 0         # (SL+1)*4 bytes

    @classmethod
    def parse(cls, data: bytes) -> Tuple["CommonHeader", bytes]:
        """Parse common header from bytes."""
        if len(data) < 12:
            raise ValueError("Insufficient data for common header")

        # First 4 bytes: Version(4) | TrafficClass(8) | FlowID(20)
        word0 = struct.unpack(">I", data[0:4])[0]
        version = (word0 >> 28) & 0xF
        traffic_class = (word0 >> 20) & 0xFF
        flow_id = word0 & 0xFFFFF

        # Second 4 bytes: NextHdr(8) | HdrLen(8) | PayLen(16)
        next_hdr, hdr_len, pay_len = struct.unpack(">BBH", data[4:8])

        # Third 4 bytes: PathType(8) | DT(2) | DL(2) | ST(2) | SL(2) | Reserved(16)
        path_type, addr_info = struct.unpack(">BB", data[8:10])
        dt = (addr_info >> 6) & 0x3
        dl = (addr_info >> 4) & 0x3
        st = (addr_info >> 2) & 0x3
        sl = addr_info & 0x3

        header = cls(
            version=version,
            traffic_class=traffic_class,
            flow_id=flow_id,
            next_header=NextHeader(next_hdr),
            header_length=hdr_len,
            payload_length=pay_len,
            path_type=PathType(path_type),
            dst_addr_type=AddrType(dt),
            dst_addr_len=dl,
            src_addr_type=AddrType(st),
            src_addr_len=sl,
        )

        return header, data[12:]

    def serialize(self) -> bytes:
        """Serialize common header to bytes."""
        # First word
        word0 = (
            (self.version & 0xF) << 28 |
            (self.traffic_class & 0xFF) << 20 |
            (self.flow_id & 0xFFFFF)
        )

        # Address info byte
        addr_info = (
            (self.dst_addr_type & 0x3) << 6 |
            (self.dst_addr_len & 0x3) << 4 |
            (self.src_addr_type & 0x3) << 2 |
            (self.src_addr_len & 0x3)
        )

        return struct.pack(
            ">IBBHBB2x",
            word0,
            self.next_header,
            self.header_length,
            self.payload_length,
            self.path_type,
            addr_info,
        )


@dataclass
class ISDAS:
    """ISD-AS identifier (8 bytes)."""
    isd: int = 0          # 16 bits
    asn: int = 0          # 48 bits

    @classmethod
    def parse(cls, data: bytes) -> "ISDAS":
        """Parse ISD-AS from 8 bytes."""
        # ISD-AS: ISD(16 bits) | AS(48 bits)
        isd = struct.unpack(">H", data[0:2])[0]
        # AS is 48 bits, stored in big-endian
        asn = struct.unpack(">Q", b"\x00\x00" + data[2:8])[0]
        return cls(isd=isd, asn=asn)

    def serialize(self) -> bytes:
        """Serialize ISD-AS to 8 bytes."""
        isd_bytes = struct.pack(">H", self.isd)
        asn_bytes = struct.pack(">Q", self.asn)[2:]  # Take last 6 bytes
        return isd_bytes + asn_bytes

    def __str__(self) -> str:
        return f"{self.isd}-{self.asn:012x}"

    @classmethod
    def from_string(cls, s: str) -> "ISDAS":
        """Parse from string format 'ISD-ASN'."""
        isd_str, asn_str = s.split("-")
        isd = int(isd_str)
        # Handle both hex (ff00:0:XXX) and decimal formats
        if ":" in asn_str:
            parts = asn_str.split(":")
            asn = int(parts[0], 16) << 32 | int(parts[1], 16) << 16 | int(parts[2], 16)
        else:
            asn = int(asn_str, 16)
        return cls(isd=isd, asn=asn)


@dataclass
class AddressHeader:
    """
    SCION Address Header (Section 3.2).

    Contains:
    - Destination ISD-AS (8 bytes)
    - Source ISD-AS (8 bytes)
    - Destination Host Address (variable)
    - Source Host Address (variable)
    """
    dst_isd_as: ISDAS = field(default_factory=ISDAS)
    src_isd_as: ISDAS = field(default_factory=ISDAS)
    dst_host: bytes = b""
    src_host: bytes = b""

    @classmethod
    def parse(cls, data: bytes, common: CommonHeader) -> Tuple["AddressHeader", bytes]:
        """Parse address header from bytes."""
        # ISD-AS are 8 bytes each
        dst_isd_as = ISDAS.parse(data[0:8])
        src_isd_as = ISDAS.parse(data[8:16])

        # Host addresses follow
        dst_len = (common.dst_addr_len + 1) * 4
        src_len = (common.src_addr_len + 1) * 4

        offset = 16
        dst_host = data[offset:offset + dst_len]
        offset += dst_len
        src_host = data[offset:offset + src_len]
        offset += src_len

        return cls(
            dst_isd_as=dst_isd_as,
            src_isd_as=src_isd_as,
            dst_host=dst_host,
            src_host=src_host,
        ), data[offset:]

    def serialize(self) -> bytes:
        """Serialize address header to bytes."""
        return (
            self.dst_isd_as.serialize() +
            self.src_isd_as.serialize() +
            self.dst_host +
            self.src_host
        )


@dataclass
class InfoField:
    """
    SCION Path Info Field (8 bytes, Section 3.3.2).

    Format:
    ┌────────┬────────┬────────┬────────┐
    │ Flags  │ Resv   │ SegID  │ SegID  │  4 bytes
    ├────────┼────────┴────────┴────────┤
    │        Timestamp                  │  4 bytes
    └───────────────────────────────────┘
    """
    flags: int = 0            # 8 bits (Bit 0: ConsDir, Bit 1: Peer)
    segment_id: int = 0       # 16 bits
    timestamp: int = 0        # 32 bits (Unix epoch seconds)

    @property
    def cons_dir(self) -> bool:
        """Construction direction flag."""
        return bool(self.flags & 0x01)

    @property
    def peer(self) -> bool:
        """Peer link flag."""
        return bool(self.flags & 0x02)

    @classmethod
    def parse(cls, data: bytes) -> "InfoField":
        """Parse info field from 8 bytes."""
        flags, _, seg_id, timestamp = struct.unpack(">BBHI", data[:8])
        return cls(flags=flags, segment_id=seg_id, timestamp=timestamp)

    def serialize(self) -> bytes:
        """Serialize info field to 8 bytes."""
        return struct.pack(">BBHI", self.flags, 0, self.segment_id, self.timestamp)


@dataclass
class HopField:
    """
    SCION Hop Field (12 bytes, Section 3.3.3).

    Format:
    ┌────────┬────────┬────────┬────────┐
    │ Flags  │ ExpTime│ ConsIngress    │  4 bytes
    ├────────┼────────┼────────────────┤
    │ ConsEgress      │ Reserved       │  4 bytes
    ├────────┴────────┴────────────────┤
    │          MAC (48 bits)           │  6 bytes (last 2 padded)
    └──────────────────────────────────┘

    Note: In actual SCION implementation, the last field is 6 bytes MAC,
    but the hop field is 12 bytes total.
    """
    flags: int = 0              # 8 bits (Bit 0: Router Alert)
    exp_time: int = 0           # 8 bits (expiry = Timestamp + (1 + ExpTime) * 24 * 60 * 60 / 256)
    cons_ingress: int = 0       # 16 bits - Interface ID
    cons_egress: int = 0        # 16 bits - Interface ID
    mac: bytes = b"\x00" * 6    # 48 bits - Truncated HMAC

    @property
    def router_alert(self) -> bool:
        """Router alert flag."""
        return bool(self.flags & 0x01)

    @classmethod
    def parse(cls, data: bytes) -> "HopField":
        """Parse hop field from 12 bytes."""
        flags, exp_time, cons_ingress, cons_egress = struct.unpack(">BBHH", data[:6])
        mac = data[6:12]
        return cls(
            flags=flags,
            exp_time=exp_time,
            cons_ingress=cons_ingress,
            cons_egress=cons_egress,
            mac=mac,
        )

    def serialize(self) -> bytes:
        """Serialize hop field to 12 bytes."""
        return struct.pack(
            ">BBHH",
            self.flags,
            self.exp_time,
            self.cons_ingress,
            self.cons_egress,
        ) + self.mac


@dataclass
class PathHeader:
    """
    SCION Path Header (Section 3.3).

    For PathType=1 (SCION Path):
    - Path Meta Header (4 bytes)
    - Info Fields (8 bytes each)
    - Hop Fields (12 bytes each)
    """
    # Path Meta Header fields
    curr_inf: int = 0           # 2 bits - Current info field index
    curr_hf: int = 0            # 6 bits - Current hop field index
    seg0_len: int = 0           # 6 bits - Number of hops in segment 0
    seg1_len: int = 0           # 6 bits - Number of hops in segment 1
    seg2_len: int = 0           # 6 bits - Number of hops in segment 2

    info_fields: List[InfoField] = field(default_factory=list)
    hop_fields: List[HopField] = field(default_factory=list)

    @classmethod
    def parse(cls, data: bytes, path_type: PathType) -> Tuple["PathHeader", bytes]:
        """Parse path header from bytes."""
        if path_type == PathType.EMPTY:
            return cls(), data

        if path_type != PathType.SCION:
            # For now, only implement SCION path type
            raise NotImplementedError(f"Path type {path_type} not implemented")

        # Parse Path Meta Header (4 bytes)
        meta = struct.unpack(">I", data[:4])[0]
        curr_inf = (meta >> 30) & 0x3
        curr_hf = (meta >> 24) & 0x3F
        seg0_len = (meta >> 18) & 0x3F
        seg1_len = (meta >> 12) & 0x3F
        seg2_len = (meta >> 6) & 0x3F

        offset = 4

        # Calculate number of info fields
        num_info = sum(1 for l in [seg0_len, seg1_len, seg2_len] if l > 0)

        # Parse Info Fields
        info_fields = []
        for _ in range(num_info):
            info_fields.append(InfoField.parse(data[offset:offset + 8]))
            offset += 8

        # Parse Hop Fields
        total_hops = seg0_len + seg1_len + seg2_len
        hop_fields = []
        for _ in range(total_hops):
            hop_fields.append(HopField.parse(data[offset:offset + 12]))
            offset += 12

        return cls(
            curr_inf=curr_inf,
            curr_hf=curr_hf,
            seg0_len=seg0_len,
            seg1_len=seg1_len,
            seg2_len=seg2_len,
            info_fields=info_fields,
            hop_fields=hop_fields,
        ), data[offset:]

    def serialize(self) -> bytes:
        """Serialize path header to bytes."""
        # Path Meta Header
        meta = (
            (self.curr_inf & 0x3) << 30 |
            (self.curr_hf & 0x3F) << 24 |
            (self.seg0_len & 0x3F) << 18 |
            (self.seg1_len & 0x3F) << 12 |
            (self.seg2_len & 0x3F) << 6
        )

        result = struct.pack(">I", meta)

        for info in self.info_fields:
            result += info.serialize()

        for hop in self.hop_fields:
            result += hop.serialize()

        return result

    def get_current_hop(self) -> Optional[HopField]:
        """Get current hop field."""
        if self.curr_hf < len(self.hop_fields):
            return self.hop_fields[self.curr_hf]
        return None


@dataclass
class SCIONHeader:
    """
    Complete SCION Packet Header.

    Provides full parsing and serialization of SCION headers,
    including support for LuciVerse extension headers.
    """
    common: CommonHeader = field(default_factory=CommonHeader)
    address: AddressHeader = field(default_factory=AddressHeader)
    path: PathHeader = field(default_factory=PathHeader)
    extensions: List[bytes] = field(default_factory=list)
    payload: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> "SCIONHeader":
        """Parse complete SCION header from bytes."""
        # Parse Common Header
        common, remaining = CommonHeader.parse(data)

        # Parse Address Header
        address, remaining = AddressHeader.parse(remaining, common)

        # Parse Path Header
        path, remaining = PathHeader.parse(remaining, common.path_type)

        # Parse Extension Headers (if any)
        extensions = []
        next_hdr = common.next_header

        while next_hdr in (NextHeader.HOP_BY_HOP, NextHeader.END_TO_END):
            if len(remaining) < 2:
                break
            ext_next_hdr = remaining[0]
            ext_len = (remaining[1] + 1) * 4  # Length in 4-byte units

            if len(remaining) < ext_len:
                break

            extensions.append(remaining[:ext_len])
            remaining = remaining[ext_len:]
            next_hdr = NextHeader(ext_next_hdr)

        return cls(
            common=common,
            address=address,
            path=path,
            extensions=extensions,
            payload=remaining,
        )

    def serialize(self) -> bytes:
        """Serialize complete SCION header to bytes."""
        result = self.common.serialize()
        result += self.address.serialize()
        result += self.path.serialize()

        for ext in self.extensions:
            result += ext

        result += self.payload
        return result

    def get_source_tier(self) -> str:
        """Get source tier based on ISD."""
        from . import get_tier_from_isd
        return get_tier_from_isd(self.address.src_isd_as.isd)

    def get_destination_tier(self) -> str:
        """Get destination tier based on ISD."""
        from . import get_tier_from_isd
        return get_tier_from_isd(self.address.dst_isd_as.isd)

    def compute_path_hash(self) -> str:
        """Compute hash of path for logging/tracking."""
        path_bytes = self.path.serialize()
        return hashlib.sha256(path_bytes).hexdigest()[:16]
