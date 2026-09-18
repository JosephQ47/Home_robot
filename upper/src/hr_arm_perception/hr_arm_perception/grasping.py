"""Turning a 2D detection plus a depth patch into a grasp candidate.

The first version deliberately does not run a grasp network. It uses the
"detection box + valid depth + constrained planar grasp" strategy the plan
fixes for known object classes (技术方案 §3.12.4): the approach direction,
pre-grasp height, opening and descent are frozen per class, and the only thing
computed here is where the object is and how the gripper should be turned.

A Cornell-trained network can later replace `plan_grasp` without touching the
gating around it — which is the part that keeps a bad candidate from moving
a real arm.

# @spec 家庭服务机器人技术方案.md#3.12.4
"""
import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float

    def valid(self) -> bool:
        return self.fx > 0.0 and self.fy > 0.0

    def deproject(self, u: float, v: float, depth_m: float):
        """Pixel + depth -> a point in the camera's optical frame."""
        return ((u - self.cx) * depth_m / self.fx,
                (v - self.cy) * depth_m / self.fy,
                depth_m)


@dataclass(frozen=True)
class ObjectGraspConfig:
    """Per-class limits, frozen by acceptance rather than chosen at runtime."""
    object_class: str
    gripper_width_m: float
    max_gripper_width_m: float
    pregrasp_height_m: float
    approach_distance_m: float
    lift_height_m: float
    min_confidence: float = 0.70


@dataclass(frozen=True)
class DepthQuality:
    min_valid_ratio: float = 0.50
    min_depth_m: float = 0.15
    max_depth_m: float = 1.20
    # A patch whose depths disagree wildly is looking at an edge or a hole, not
    # at a graspable face.
    max_spread_m: float = 0.08


@dataclass(frozen=True)
class GraspCandidate:
    object_class: str
    confidence: float
    position: tuple            # (x, y, z) in the camera optical frame
    grasp_angle: float
    gripper_width: float
    quality: float
    depth_valid_ratio: float


@dataclass(frozen=True)
class Rejected:
    reason: str


def depth_statistics(samples, quality: DepthQuality):
    """Median depth of the in-range samples, plus how many were usable.

    The median is used rather than the mean because a single stray reading off
    the object's edge would drag a mean toward the background.
    """
    total = len(samples)
    usable = [d for d in samples
              if d == d and d > 0.0 and quality.min_depth_m <= d <= quality.max_depth_m]
    ratio = 0.0 if total == 0 else len(usable) / total
    if not usable:
        return None, ratio, 0.0
    spread = max(usable) - min(usable)
    return statistics.median(usable), ratio, spread


def plan_grasp(object_class, confidence, bbox, depth_samples, intrinsics, config,
               quality=DepthQuality()):
    """Build one grasp candidate, or say precisely why there is none.

    `bbox` is (center_u, center_v, width_px, height_px) from the detector, and
    `depth_samples` are the depth values inside it, in metres.
    """
    if not intrinsics.valid():
        return Rejected('camera_info_invalid')
    if confidence < config.min_confidence:
        return Rejected('low_confidence')
    depth, ratio, spread = depth_statistics(depth_samples, quality)
    if depth is None:
        # Transparent, glossy and very thin objects land here. The plan requires
        # they come out as observe-only, never as a grasp attempt.
        return Rejected('no_valid_depth')
    if ratio < quality.min_valid_ratio:
        return Rejected('depth_too_sparse')
    if spread > quality.max_spread_m:
        return Rejected('depth_inconsistent')

    u, v, w_px, h_px = bbox
    position = intrinsics.deproject(u, v, depth)

    # Grasp across the object's shorter image axis: that is the direction the
    # jaws have to close for the object to fit between them.
    grasp_angle = 0.0 if w_px <= h_px else math.pi / 2.0
    short_px = min(w_px, h_px)
    width_m = short_px * depth / intrinsics.fx
    # Open a little wider than the object, but never past the mechanical limit.
    opening = min(width_m * 1.15, config.max_gripper_width_m)
    if width_m > config.max_gripper_width_m:
        return Rejected('object_wider_than_gripper')

    quality_score = min(1.0, confidence * ratio * (1.0 - spread / quality.max_spread_m))
    return GraspCandidate(object_class=object_class, confidence=confidence,
                          position=position, grasp_angle=grasp_angle,
                          gripper_width=opening, quality=max(0.0, quality_score),
                          depth_valid_ratio=ratio)


def best_candidate(candidates):
    """Highest quality wins; ties are broken by detector confidence."""
    real = [c for c in candidates if isinstance(c, GraspCandidate)]
    if not real:
        return None
    return max(real, key=lambda c: (c.quality, c.confidence))
