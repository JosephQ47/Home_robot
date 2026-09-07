"""OpenCTR X-Protocol used by the already-tested STM32 serial link.

Frame format (all multi-byte values are big endian)::

    AA 55 | LEN | ID | DATA... | SUM

``LEN`` is the complete frame length and ``SUM`` is the low byte of the
sum of every preceding byte.  This module deliberately implements the PDF
protocol, not the newer proposal in the architecture document.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

FRAME_HEAD = b"\xAA\x55"
ID_URX_VEL = 0x50
ID_UTX_DATA = 0x10
VELOCITY_DATA_LEN = 6
STATE_DATA_LEN = 20


class ProtocolError(ValueError):
    """Raised when a complete protocol frame is malformed."""


@dataclass(frozen=True)
class VelocityCommand:
    """Command units match the controller: mm/s and mrad/s."""

    vx_mm_s: int = 0
    vy_mm_s: int = 0
    wz_mrad_s: int = 0


@dataclass(frozen=True)
class StateFrame:
    """The 0x10 state payload described in the source reading guide."""

    accel: tuple[int, int, int]
    gyro: tuple[int, int, int]
    velocity: tuple[int, int, int]
    battery_x100: int


def _check_int16(value: int, name: str) -> None:
    if not -32768 <= value <= 32767:
        raise ProtocolError(f"{name} out of int16 range: {value}")


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def encode_frame(message_id: int, payload: bytes) -> bytes:
    length = len(payload) + 5
    if not 5 <= length <= 255:
        raise ProtocolError(f"invalid frame length: {length}")
    body = FRAME_HEAD + bytes((length, message_id)) + payload
    return body + bytes((checksum(body),))


def encode_velocity_frame(command: VelocityCommand) -> bytes:
    for name, value in vars(command).items():
        _check_int16(value, name)
    return encode_frame(
        ID_URX_VEL,
        struct.pack(">hhh", command.vx_mm_s, command.vy_mm_s, command.wz_mrad_s),
    )


def decode_state_frame(frame: bytes) -> StateFrame:
    if len(frame) < 5 or frame[:2] != FRAME_HEAD:
        raise ProtocolError("invalid frame header")
    if frame[2] != len(frame):
        raise ProtocolError("frame length does not match LEN")
    if frame[3] != ID_UTX_DATA:
        raise ProtocolError(f"unexpected state message id: 0x{frame[3]:02X}")
    if len(frame[4:-1]) != STATE_DATA_LEN:
        raise ProtocolError("invalid 0x10 payload length")
    if frame[-1] != checksum(frame[:-1]):
        raise ProtocolError("checksum mismatch")
    values = struct.unpack(">hhhhhhhhhh", frame[4:-1])
    return StateFrame(values[0:3], values[3:6], values[6:9], values[9])


class XProtocolParser:
    """Incremental parser safe against noise, split frames and bad lengths."""

    def __init__(self, max_frame_length: int = 64) -> None:
        self._buffer = bytearray()
        self.max_frame_length = max_frame_length
        self.bad_frames = 0

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer.extend(data)
        frames: list[bytes] = []
        while True:
            head = self._buffer.find(FRAME_HEAD)
            if head < 0:
                self._buffer[:] = self._buffer[-1:]
                break
            if head:
                del self._buffer[:head]
            if len(self._buffer) < 3:
                break
            length = self._buffer[2]
            if length < 5 or length > self.max_frame_length:
                self.bad_frames += 1
                del self._buffer[:2]
                continue
            if len(self._buffer) < length:
                break
            frame = bytes(self._buffer[:length])
            del self._buffer[:length]
            if frame[-1] != checksum(frame[:-1]):
                self.bad_frames += 1
                continue
            frames.append(frame)
        return frames
