"""PC-side STM32 bridge, independent of ROS 2 and usable in a bench test."""

from __future__ import annotations

from dataclasses import asdict
import threading
import time
from typing import Protocol

from .protocol import (
    ID_UTX_DATA,
    StateFrame,
    VelocityCommand,
    XProtocolParser,
    decode_state_frame,
    encode_velocity_frame,
)


class ByteTransport(Protocol):
    def write(self, data: bytes) -> int: ...

    def read_available(self) -> bytes: ...


class SerialBridge:
    """Transport adapter used later by a ROS 2 node or the web backend.

    The lower controller owns the hard safety timeout.  The PC-side timeout
    here is only a diagnostic state and causes a best-effort zero command when
    ``stop()`` is called; it never replaces STM32 safety logic.
    """

    def __init__(self, transport: ByteTransport) -> None:
        self.transport = transport
        self.parser = XProtocolParser()
        self.last_state: StateFrame | None = None
        self.last_rx_monotonic: float | None = None
        self.rx_frames = 0
        self.rx_errors = 0
        self._lock = threading.Lock()

    def send_velocity(self, vx_mm_s: int, wz_mrad_s: int, vy_mm_s: int = 0) -> None:
        command = VelocityCommand(vx_mm_s, vy_mm_s, wz_mrad_s)
        with self._lock:
            self.transport.write(encode_velocity_frame(command))

    def poll(self) -> list[StateFrame]:
        states: list[StateFrame] = []
        for frame in self.parser.feed(self.transport.read_available()):
            if frame[3] != ID_UTX_DATA:
                continue
            try:
                state = decode_state_frame(frame)
            except ValueError:
                self.rx_errors += 1
                continue
            self.last_state = state
            self.last_rx_monotonic = time.monotonic()
            self.rx_frames += 1
            states.append(state)
        return states

    def snapshot(self) -> dict[str, object]:
        state = asdict(self.last_state) if self.last_state else None
        age = None
        if self.last_rx_monotonic is not None:
            age = max(0.0, time.monotonic() - self.last_rx_monotonic)
        return {
            "connected": self.last_rx_monotonic is not None,
            "state": state,
            "state_age_seconds": age,
            "rx_frames": self.rx_frames,
            "rx_errors": self.rx_errors,
            "parser_bad_frames": self.parser.bad_frames,
        }

    def stop(self) -> None:
        """Best-effort PC stop command before closing the transport."""
        self.send_velocity(0, 0)
