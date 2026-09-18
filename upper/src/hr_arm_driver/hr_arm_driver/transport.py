"""Where the servo frames actually go.

Two backends: a real serial port, and a mock controller that integrates the
commanded joints toward their targets so the whole arm chain can be exercised
on a PC. The mock is explicit about being a mock — it never pretends a fault
it cannot have, and it is selected by an obvious parameter rather than by
silently falling back when the port is missing.

# @spec 家庭服务机器人技术方案.md#3.12.1
"""
import struct
import time
from dataclasses import dataclass, field

from .protocol import (JOINTS, MSG_SET_GRIPPER, MSG_SET_JOINTS, MSG_STOP,
                       Decoder, encode_status)


class SerialTransport:
    """Real link. Reconnects on its own; never blocks the ROS executor."""

    def __init__(self, port, baudrate, logger=None):
        import serial  # imported lazily so the mock backend needs no pyserial
        self._serial_module = serial
        self.port, self.baudrate, self.logger = port, baudrate, logger
        self.link = None
        self.reconnects = 0

    def _open(self):
        if self.link is not None:
            return True
        try:
            self.link = self._serial_module.Serial(self.port, self.baudrate, timeout=0)
            self.reconnects += 1
            return True
        except Exception as exc:  # noqa: BLE001 - any open failure is just "not yet"
            if self.logger:
                self.logger.warning(f'arm serial {self.port} unavailable: {exc}')
            self.link = None
            return False

    def write(self, frame: bytes) -> bool:
        if not self._open():
            return False
        try:
            self.link.write(frame)
            return True
        except Exception:  # noqa: BLE001
            self.link = None
            return False

    def read(self) -> bytes:
        if not self._open():
            return b''
        try:
            return self.link.read(4096)
        except Exception:  # noqa: BLE001
            self.link = None
            return b''

    def close(self):
        if self.link is not None:
            try:
                self.link.close()
            finally:
                self.link = None


@dataclass
class MockController:
    """A servo controller that exists only in this process.

    Joints ease toward their targets at a fixed rate so motion takes real time,
    which is what makes the arm state machine's timeouts meaningful in a PC run.
    """
    max_joint_speed: float = 1.2       # rad/s
    max_gripper_speed: float = 0.08    # m/s
    positions: list = field(default_factory=lambda: [0.0] * JOINTS)
    targets: list = field(default_factory=lambda: [0.0] * JOINTS)
    gripper: float = 0.0
    gripper_target: float = 0.0
    fault_word: int = 0
    decoder: Decoder = field(default_factory=Decoder)
    _last: float = field(default_factory=time.monotonic)
    _out: bytearray = field(default_factory=bytearray)

    def write(self, frame: bytes) -> bool:
        self._consume(frame)
        return True

    def _consume(self, frame):
        # Reuse the wire format rather than a side channel, so the mock exercises
        # the same encode path the real controller would receive.
        if len(frame) < 4 or frame[:2] != b'\xa5\x5a':
            return
        msg_id, length = frame[2], frame[3]
        payload = frame[4:4 + length]
        if msg_id == MSG_SET_JOINTS and len(payload) == struct.calcsize('<6fH'):
            values = struct.unpack('<6fH', payload)
            self.targets = list(values[:JOINTS])
        elif msg_id == MSG_SET_GRIPPER and len(payload) == struct.calcsize('<fH'):
            self.gripper_target = struct.unpack('<fH', payload)[0]
        elif msg_id == MSG_STOP:
            self.targets = list(self.positions)
            self.gripper_target = self.gripper

    def _step(self):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        moving = False
        for i, target in enumerate(self.targets):
            delta = target - self.positions[i]
            step = self.max_joint_speed * dt
            if abs(delta) <= step:
                self.positions[i] = target
            else:
                self.positions[i] += step if delta > 0 else -step
                moving = True
        delta = self.gripper_target - self.gripper
        step = self.max_gripper_speed * dt
        if abs(delta) <= step:
            self.gripper = self.gripper_target
        else:
            self.gripper += step if delta > 0 else -step
            moving = True
        return moving

    def read(self) -> bytes:
        moving = self._step()
        # Current rises while moving: enough for the state machine's load check
        # to have something to read, not a claim about any real servo.
        currents = [0.6 if moving else 0.15] * JOINTS
        return encode_status(self.positions, currents, self.gripper,
                             self.fault_word, moving)

    def close(self):
        pass


def make_transport(kind, port, baudrate, logger=None):
    if kind == 'mock':
        if logger:
            logger.warning('hr_arm_driver is using the MOCK servo controller: '
                           'joint states are simulated, not measured')
        return MockController()
    if kind == 'serial':
        return SerialTransport(port, baudrate, logger)
    raise ValueError(f'unknown arm transport "{kind}"; use "serial" or "mock"')
