"""Pure arbitration logic for the single automatic velocity source.

Kept free of rclpy so the safety rules (MUX-1..MUX-8 in
docs/features/hr_motion_mux.md) can be tested without a ROS graph.

# @spec 家庭服务机器人技术方案.md#2.2
"""
from dataclasses import dataclass, field

ZERO = 0
NAVIGATING = 1
FOLLOWING = 2
DOCKING = 3

# MUX-1: which source each phase authorises. A phase absent from this map
# authorises nothing, which is the safe default for future phase values.
NAV_PHASES = frozenset({NAVIGATING, FOLLOWING})
DOCK_PHASES = frozenset({DOCKING})

NAV = 'nav'
DOCK = 'dock'


@dataclass(frozen=True)
class Limits:
    source_timeout_sec: float = 0.2
    phase_timeout_sec: float = 1.0
    zero_hold_sec: float = 0.3


@dataclass
class Command:
    """One velocity candidate plus the time it arrived."""
    vx: float = 0.0
    wz: float = 0.0
    stamp: float = float('-inf')


@dataclass
class Decision:
    vx: float
    wz: float
    source: str | None
    reason: str


@dataclass
class MotionMux:
    limits: Limits = field(default_factory=Limits)
    nav: Command = field(default_factory=Command)
    dock: Command = field(default_factory=Command)
    phase: int = ZERO
    phase_stamp: float = float('-inf')
    phase_seq: int = 0
    _seq_seen: bool = False
    # MUX-2: set whenever the authorised phase changes; blocks forwarding until
    # zero_hold_sec of zeros has been published.
    zero_until: float = float('-inf')

    def on_nav(self, vx: float, wz: float, now: float) -> None:
        self.nav = Command(vx, wz, now)

    def on_dock(self, vx: float, wz: float, now: float) -> None:
        self.dock = Command(vx, wz, now)

    def on_phase(self, phase: int, source_seq: int, now: float, zero_required: bool = False) -> bool:
        """Accept a phase authorisation. Returns False when the message is ignored.

        MUX-5: source_seq must strictly advance. A repeated or rewound seq means
        the message is a late straggler from a phase we have already left, so
        honouring it could re-authorise a source the task manager revoked.
        """
        if self._seq_seen and source_seq <= self.phase_seq:
            return False
        changed = phase != self.phase
        self._seq_seen = True
        self.phase_seq = source_seq
        self.phase_stamp = now
        if changed or zero_required:
            self.phase = phase
            self.zero_until = now + self.limits.zero_hold_sec
        return True

    def _authorised(self) -> str | None:
        if self.phase in NAV_PHASES:
            return NAV
        if self.phase in DOCK_PHASES:
            return DOCK
        return None

    def decide(self, now: float) -> Decision:
        """Compute the value to publish this tick. Never raises; defaults to zero."""
        if now - self.phase_stamp > self.limits.phase_timeout_sec:
            # MUX-4: no live authorisation at all.
            return Decision(0.0, 0.0, None, 'phase_stale')
        source = self._authorised()
        if source is None:
            return Decision(0.0, 0.0, None, 'phase_zero')
        if now < self.zero_until:
            # MUX-2: still inside the mandatory zero window after a switch.
            return Decision(0.0, 0.0, None, 'switch_zero_hold')
        command = self.nav if source is NAV else self.dock
        if now - command.stamp > self.limits.source_timeout_sec:
            # MUX-3: the authorised source went quiet; never reuse its last value.
            return Decision(0.0, 0.0, None, f'{source}_stale')
        # MUX-6 is enforced by the caller building the Twist: only vx/wz are carried.
        return Decision(command.vx, command.wz, source, 'forward')
