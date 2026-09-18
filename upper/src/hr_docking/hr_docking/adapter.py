"""Gating and pose maths for turning an AprilTag sighting into a dock pose.

Free of rclpy and of apriltag_msgs so rules DOCK-1..DOCK-7 in
docs/features/hr_docking.md can be tested without hardware or a ROS graph.

Detecting the tag says only "the charger is over there". It never means the
robot has touched the contacts, and it never means charging has begun — that
claim belongs to /battery_state alone.

# @spec 家庭服务机器人技术方案.md#3.1.4
"""
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pose2D:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class DockConfig:
    dock_id: str = 'home_dock'
    tag_id: int = 0
    # Offset from the tag frame to the point the robot must reach for the
    # spring contacts to meet. Measured by calibration, never by tape.
    tag_to_contact: Pose2D = Pose2D()
    tag_timeout_sec: float = 0.5
    max_jump_xy_m: float = 0.15
    max_jump_yaw_rad: float = 0.35
    max_consecutive_jumps: int = 3
    min_consecutive_detections: int = 3


@dataclass(frozen=True)
class Rejected:
    reason: str


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def compose(base: Pose2D, offset: Pose2D) -> Pose2D:
    """Apply `offset`, expressed in `base`'s own frame, to `base`."""
    c, s = math.cos(base.yaw), math.sin(base.yaw)
    return Pose2D(base.x + c * offset.x - s * offset.y,
                  base.y + s * offset.x + c * offset.y,
                  wrap_angle(base.yaw + offset.yaw))


@dataclass
class DockPoseAdapter:
    config: DockConfig = field(default_factory=DockConfig)
    _last: Pose2D | None = None
    _last_stamp: float = float('-inf')
    _streak: int = 0
    _jumps: int = 0
    failed: bool = False

    def reset(self) -> None:
        self._last = None
        self._last_stamp = float('-inf')
        self._streak = 0
        self._jumps = 0
        self.failed = False

    def update(self, tag_id: int, pose: Pose2D, stamp: float,
               camera_info_valid: bool = True) -> Pose2D | Rejected:
        """Consume one detection. Returns the dock pose to publish, or why not."""
        if self.failed:
            return Rejected('failed_latched')
        if not camera_info_valid:
            # DOCK-4: without trustworthy intrinsics the tag pose is meaningless.
            return Rejected('camera_info_invalid')
        if tag_id != self.config.tag_id:
            # DOCK-1: an unregistered tag is somebody else's marker.
            return Rejected('tag_id_mismatch')
        if self._last is not None:
            jump_xy = math.hypot(pose.x - self._last.x, pose.y - self._last.y)
            jump_yaw = abs(wrap_angle(pose.yaw - self._last.yaw))
            if jump_xy > self.config.max_jump_xy_m or jump_yaw > self.config.max_jump_yaw_rad:
                # DOCK-3: a physically impossible jump means a misdetection.
                self._jumps += 1
                self._streak = 0
                if self._jumps >= self.config.max_consecutive_jumps:
                    self.failed = True
                    return Rejected('pose_jump_latched')
                return Rejected('pose_jump')
        self._jumps = 0
        self._last, self._last_stamp = pose, stamp
        self._streak += 1
        if self._streak < self.config.min_consecutive_detections:
            # DOCK-7: one lucky frame must not start a docking approach.
            return Rejected('warming_up')
        # DOCK-5
        return compose(pose, self.config.tag_to_contact)

    def expired(self, now: float) -> bool:
        """DOCK-2: past the timeout there is no dock pose, not an old one."""
        return now - self._last_stamp > self.config.tag_timeout_sec

    def tick(self, now: float) -> None:
        """Drop the tracking state once the last sighting has aged out."""
        if self.expired(now):
            self._last = None
            self._streak = 0
