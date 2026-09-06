"""HomeRobot V1 wire protocol; authoritative layout is docs/protocol/README.md."""
from __future__ import annotations
from dataclasses import dataclass
import struct

SOF = b"\xA5\x5A"
VERSION = 1
MAX_PAYLOAD = 96
CMD_MOTION = 0x01
_FIXED_SIZE = 14


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Frame:
    message_id: int
    sequence: int
    timestamp_ms: int
    payload: bytes


def encode_frame(message_id: int, sequence: int, timestamp_ms: int, payload: bytes = b"") -> bytes:
    if not 0 <= message_id <= 0xFF or not 0 <= sequence <= 0xFFFF or not 0 <= timestamp_ms <= 0xFFFFFFFF:
        raise ValueError("frame field outside wire range")
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    body = struct.pack("<BBHHI", VERSION, message_id, len(payload), sequence, timestamp_ms) + payload
    return SOF + body + struct.pack("<H", crc16_ccitt_false(body))


def encode_motion(sequence: int, timestamp_ms: int, vx_mm_s: int, wz_mrad_s: int, enable: bool) -> bytes:
    for value in (vx_mm_s, wz_mrad_s):
        if not -(1 << 31) <= value < (1 << 31):
            raise ValueError("motion value outside int32")
    return encode_frame(CMD_MOTION, sequence, timestamp_ms,
                        struct.pack("<iiBB", vx_mm_s, wz_mrad_s, int(enable), 0))


class Parser:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_frames = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        frames = []
        while True:
            start = self.buffer.find(SOF)
            if start < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(SOF[:1]) else b""
                break
            del self.buffer[:start]
            if len(self.buffer) < 6:
                break
            version, message_id, length = struct.unpack_from("<BBH", self.buffer, 2)
            if length > MAX_PAYLOAD:
                self.bad_frames += 1
                del self.buffer[:2]
                continue
            total = _FIXED_SIZE + length
            if len(self.buffer) < total:
                break
            raw = bytes(self.buffer[:total])
            del self.buffer[:total]
            expected = struct.unpack_from("<H", raw, total - 2)[0]
            if version != VERSION or expected != crc16_ccitt_false(raw[2:-2]):
                self.bad_frames += 1
                continue
            _, _, _, sequence, stamp = struct.unpack_from("<BBHHI", raw, 2)
            frames.append(Frame(message_id, sequence, stamp, raw[12:-2]))
        return frames
