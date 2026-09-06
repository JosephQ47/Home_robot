"""The already-tested OpenCTR X-Protocol used by the STM32 firmware."""

from __future__ import annotations

from dataclasses import dataclass
import struct

HEAD = b"\xAA\x55"
ID_VELOCITY = 0x50
ID_STATE = 0x10


@dataclass(frozen=True)
class State:
    accel: tuple[int, int, int]
    gyro: tuple[int, int, int]
    velocity: tuple[int, int, int]
    battery_x100: int


def _sum(data: bytes) -> int:
    return sum(data) & 0xFF


def velocity_frame(vx_mm_s: int, vy_mm_s: int, wz_mrad_s: int) -> bytes:
    values = (vx_mm_s, vy_mm_s, wz_mrad_s)
    if not all(-32768 <= value <= 32767 for value in values):
        raise ValueError("velocity does not fit int16")
    payload = struct.pack(">hhh", *values)
    body = HEAD + bytes((len(payload) + 5, ID_VELOCITY)) + payload
    return body + bytes((_sum(body),))


def decode_state(frame: bytes) -> State:
    if len(frame) != 25 or frame[:2] != HEAD or frame[2] != 25:
        raise ValueError("invalid 0x10 frame length or header")
    if frame[3] != ID_STATE or frame[-1] != _sum(frame[:-1]):
        raise ValueError("invalid 0x10 frame id or checksum")
    values = struct.unpack(">hhhhhhhhhh", frame[4:-1])
    return State(values[:3], values[3:6], values[6:9], values[9])


class Parser:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.bad_frames = 0

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        result: list[bytes] = []
        while True:
            start = self.buffer.find(HEAD)
            if start < 0:
                self.buffer[:] = self.buffer[-1:]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 3:
                break
            length = self.buffer[2]
            if length < 5 or length > 64:
                self.bad_frames += 1
                del self.buffer[:2]
                continue
            if len(self.buffer) < length:
                break
            frame = bytes(self.buffer[:length])
            del self.buffer[:length]
            if frame[-1] != _sum(frame[:-1]):
                self.bad_frames += 1
                continue
            result.append(frame)
        return result
