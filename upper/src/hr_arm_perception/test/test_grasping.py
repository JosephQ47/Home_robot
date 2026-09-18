"""技术方案 §3.12.4: depth gating and the constrained planar grasp."""
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_arm_perception.grasping import (CameraIntrinsics, DepthQuality,  # noqa: E402
                                        GraspCandidate, ObjectGraspConfig, Rejected,
                                        best_candidate, depth_statistics, plan_grasp)

K = CameraIntrinsics(fx=600.0, fy=600.0, cx=320.0, cy=240.0)
CFG = ObjectGraspConfig(object_class='杯子', gripper_width_m=0.06,
                        max_gripper_width_m=0.09, pregrasp_height_m=0.12,
                        approach_distance_m=0.08, lift_height_m=0.10,
                        min_confidence=0.70)
Q = DepthQuality(min_valid_ratio=0.50, min_depth_m=0.15, max_depth_m=1.20,
                 max_spread_m=0.08)
BBOX = (320.0, 240.0, 40.0, 70.0)


def depths(value, n=100, bad=0):
    return [value] * (n - bad) + [float('nan')] * bad


def test_good_frame_yields_a_candidate():
    out = plan_grasp('杯子', 0.9, BBOX, depths(0.40), K, CFG, Q)
    assert isinstance(out, GraspCandidate)
    assert out.position == pytest.approx((0.0, 0.0, 0.40))


def test_invalid_intrinsics_are_refused():
    out = plan_grasp('杯子', 0.9, BBOX, depths(0.40), CameraIntrinsics(0, 0, 0, 0), CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'camera_info_invalid'


def test_confidence_boundary():
    assert isinstance(plan_grasp('杯子', 0.70, BBOX, depths(0.40), K, CFG, Q), GraspCandidate)
    out = plan_grasp('杯子', 0.6999, BBOX, depths(0.40), K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'low_confidence'


def test_transparent_object_produces_no_grasp():
    """All-NaN depth is what glass returns. It must not become a grasp attempt."""
    out = plan_grasp('杯子', 0.95, BBOX, [float('nan')] * 100, K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'no_valid_depth'


def test_sparse_depth_is_refused_at_the_boundary():
    assert isinstance(plan_grasp('杯子', 0.9, BBOX, depths(0.40, 100, bad=50), K, CFG, Q),
                      GraspCandidate)
    out = plan_grasp('杯子', 0.9, BBOX, depths(0.40, 100, bad=51), K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'depth_too_sparse'


def test_inconsistent_depth_is_refused():
    """Half on the object, half on the far wall: an edge, not a graspable face."""
    out = plan_grasp('杯子', 0.9, BBOX, [0.40] * 50 + [0.60] * 50, K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'depth_inconsistent'


def test_out_of_range_depth_counts_as_invalid():
    out = plan_grasp('杯子', 0.9, BBOX, depths(2.0), K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'no_valid_depth'


def test_object_wider_than_the_gripper_is_refused():
    wide = (320.0, 240.0, 400.0, 400.0)
    out = plan_grasp('杯子', 0.9, wide, depths(0.40), K, CFG, Q)
    assert isinstance(out, Rejected) and out.reason == 'object_wider_than_gripper'


def test_grasp_closes_across_the_shorter_axis():
    tall = plan_grasp('杯子', 0.9, (320.0, 240.0, 40.0, 70.0), depths(0.40), K, CFG, Q)
    wide = plan_grasp('杯子', 0.9, (320.0, 240.0, 70.0, 40.0), depths(0.40), K, CFG, Q)
    assert tall.grasp_angle == 0.0
    assert wide.grasp_angle == pytest.approx(math.pi / 2)


def test_opening_never_exceeds_the_mechanical_limit():
    out = plan_grasp('杯子', 0.9, (320.0, 240.0, 130.0, 200.0), depths(0.40), K, CFG, Q)
    assert out.gripper_width <= CFG.max_gripper_width_m


def test_offcentre_detection_deprojects_off_axis():
    out = plan_grasp('杯子', 0.9, (380.0, 240.0, 40.0, 70.0), depths(0.50), K, CFG, Q)
    assert out.position[0] == pytest.approx((380 - 320) * 0.50 / 600.0)


def test_median_ignores_a_stray_background_reading():
    depth, ratio, _ = depth_statistics([0.40] * 99 + [1.10], Q)
    assert depth == pytest.approx(0.40)
    assert ratio == 1.0


def test_empty_sample_set_is_not_a_division_by_zero():
    assert depth_statistics([], Q) == (None, 0.0, 0.0)


def test_best_candidate_picks_the_highest_quality():
    a = plan_grasp('杯子', 0.75, BBOX, depths(0.40), K, CFG, Q)
    b = plan_grasp('杯子', 0.95, BBOX, depths(0.40), K, CFG, Q)
    assert best_candidate([a, b, Rejected('x')]) is b


def test_best_candidate_of_nothing_is_none():
    assert best_candidate([Rejected('a'), Rejected('b')]) is None
