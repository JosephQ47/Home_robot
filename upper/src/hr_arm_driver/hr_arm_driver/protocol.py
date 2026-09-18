"""Framing for the link to the independent servo controller.

The controller has not been selected yet, so what is fixed here is the *shape*
of the conversation rather than a vendor's byte layout: a length-prefixed,
CRC-checked frame carrying six joint targets plus a gripper command, and a
status frame coming back. Swapping in a vendor protocol means replacing this
module, not the node around it.

What must not move into the controller's protocol either way: joint limits,
over-current cutoff and action timeout stay *in the controller*, close to the
hardware, where a hung RK3588 cannot disable them.

# @spec 家庭服务机器人技术方案.md#3.12.1
"""
import struct
from dataclasses import dataclass, field

SOF = b'\xa5\x5a'
JOINTS = 6

MSG_SET_JOINTS = 0x01
MSG_SET_GRIPPER = 0x02
MSG_STOP = 0x03
MSG_STATUS = 0x81

# Bit positions in the status frame's fault word.
FAULT_BITS = {
    0: 'servo_overcurrent',
    1: 'servo_stall',
    2: 'joint_limit_exceeded',
    3: 'action_timeout',
    4: 'communication_lost',
    5: 'power_fault',
}


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE, the same polynomial the chassis link uses."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode(msg_id: int, payload: bytes) -> bytes:
    body = bytes([msg_id, len(payload)]) + payload
    return SOF + body + struct.pack('<H', crc16(body))


def encode_joints(positions, duration_ms: int) -> bytes:
    """Six joint angles in radians, plus how long the move may take."""
    if len(positions) != JOINTS:
        raise ValueError(f'expected {JOINTS} joint positions, got {len(positions)}')
    if duration_ms <= 0:
        raise ValueError('duration_ms must be positive')
    payload = struct.pack('<6fH', *[float(p) for p in positions], int(duration_ms))
    return encode(MSG_SET_JOINTS, payload)


def encode_gripper(width_m: float, duration_ms: int) -> bytes:
    return encode(MSG_SET_GRIPPER, struct.pack('<fH', float(width_m), int(duration_ms)))


def encode_stop() -> bytes:
    """Halt the trajectory where it is. Sent on every abort path."""
    return encode(MSG_STOP, b'')


@dataclass(frozen=True)
class Status:
    positions: tuple
    currents: tuple
    gripper_width: float
    fault_word: int
    moving: bool

    @property
    def faults(self):
        return tuple(name for bit, name in sorted(FAULT_BITS.items())
                     if self.fault_word & (1 << bit))

    @property
    def healthy(self) -> bool:
        return self.fault_word == 0


@dataclass
class Decoder:
    """Incremental frame decoder: feed it bytes, get whole valid frames back."""
    buffer: bytearray = field(default_factory=bytearray)
    crc_errors: int = 0
    dropped_bytes: int = 0
    max_buffer: int = 4096

    def feed(self, chunk: bytes):
        """Return every complete, CRC-valid status frame in the stream so far."""
        self.buffer.extend(chunk)
        if len(self.buffer) > self.max_buffer:
            # A stream that never syncs must not grow without bound.
            self.dropped_bytes += len(self.buffer) - self.max_buffer
            del self.buffer[:len(self.buffer) - self.max_buffer]
        out = []
        while True:
            start = self.buffer.find(SOF)
            if start < 0:
                self.dropped_bytes += max(0, len(self.buffer) - 1)
                del self.buffer[:max(0, len(self.buffer) - 1)]
                return out
            if start:
                self.dropped_bytes += start
                del self.buffer[:start]
            if len(self.buffer) < 4:
                return out
            msg_id, length = self.buffer[2], self.buffer[3]
            total = 2 + 2 + length + 2
            if len(self.buffer) < total:
                return out
            body = bytes(self.buffer[2:2 + 2 + length])
            got = struct.unpack('<H', bytes(self.buffer[2 + 2 + length:total]))[0]
            if crc16(body) != got:
                # Resync past this SOF rather than trusting the claimed length.
                self.crc_errors += 1
                del self.buffer[:2]
                continue
            del self.buffer[:total]
            if msg_id == MSG_STATUS:
                decoded = decode_status(body[2:])
                if decoded is not None:
                    out.append(decoded)
    

def decode_status(payload: bytes):
    expected = struct.calcsize('<6f6ffHB')
    if len(payload) != expected:
        return None
    values = struct.unpack('<6f6ffHB', payload)
    return Status(positions=values[0:6], currents=values[6:12],
                  gripper_width=values[12], fault_word=values[13],
                  moving=bool(values[14]))


def encode_status(positions, currents, gripper_width, fault_word=0, moving=False) -> bytes:
    """Used by the mock controller and by the tests."""
    payload = struct.pack('<6f6ffHB', *[float(p) for p in positions],
                          *[float(c) for c in currents], float(gripper_width),
                          int(fault_word), 1 if moving else 0)
    return encode(MSG_STATUS, payload)
