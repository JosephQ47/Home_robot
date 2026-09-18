"""Quality gating and ground removal for the Gemini 2 point cloud.

This is an *auxiliary* obstacle source for the Nav2 local costmap. The 2D SLAM,
localisation and the Collision Monitor stop zone all keep using the S3 /scan
only, so a failure here degrades the robot rather than disabling it.

Pure Python so rules DO-1..DO-7 in docs/features/hr_depth_obstacle.md are
testable without a camera.

# @spec 家庭服务机器人技术方案.md#3.2
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GateConfig:
    cloud_timeout_sec: float = 0.3
    min_valid_ratio: float = 0.30
    min_range_m: float = 0.20
    max_range_m: float = 4.00
    ground_height_m: float = 0.0
    ground_tolerance_m: float = 0.03
    obstacle_min_height_m: float = 0.05
    obstacle_max_height_m: float = 1.20


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    reason: str
    points: tuple = ()


def frame_is_fresh(stamp: float, now: float, config: GateConfig) -> bool:
    """DO-1: equal to the timeout is still fresh; past it is not."""
    return now - stamp <= config.cloud_timeout_sec


def valid_ratio(total: int, valid: int) -> float:
    return 0.0 if total <= 0 else valid / total


def filter_points(points, config: GateConfig):
    """Keep points that are in range, off the ground and inside the height window.

    `points` is an iterable of (x, y, z) in base_link: x forward, z up.
    """
    kept = []
    ground_top = config.ground_height_m + config.ground_tolerance_m
    for x, y, z in points:
        distance = (x * x + y * y) ** 0.5
        if distance < config.min_range_m or distance > config.max_range_m:
            continue  # DO-3
        if z <= ground_top:
            continue  # DO-4
        if z < config.obstacle_min_height_m or z > config.obstacle_max_height_m:
            continue  # DO-5
        kept.append((x, y, z))
    return kept


def gate_frame(points, total_pixels: int, valid_pixels: int, stamp: float,
               now: float, config: GateConfig) -> GateResult:
    """Decide whether this frame may be published at all, and what survives."""
    if not frame_is_fresh(stamp, now, config):
        return GateResult(False, 'stale', ())
    ratio = valid_ratio(total_pixels, valid_pixels)
    if ratio < config.min_valid_ratio:
        # DO-2: a mostly-empty depth frame is not evidence of free space.
        # Transparent and glossy surfaces fail exactly this way, so the frame is
        # dropped rather than published as "nothing there" (DO-7).
        return GateResult(False, 'low_valid_ratio', ())
    return GateResult(True, 'ok', tuple(filter_points(points, config)))
