"""Rules DO-1..DO-7 from docs/features/hr_depth_obstacle.md."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_depth_obstacle.gating import (GateConfig, filter_points, frame_is_fresh,  # noqa: E402
                                      gate_frame, valid_ratio)

CFG = GateConfig(cloud_timeout_sec=0.3, min_valid_ratio=0.30, min_range_m=0.2, max_range_m=4.0,
                 ground_height_m=0.0, ground_tolerance_m=0.03,
                 obstacle_min_height_m=0.05, obstacle_max_height_m=1.2)


def test_freshness_boundary_is_inclusive():
    assert frame_is_fresh(0.0, 0.3, CFG)
    assert not frame_is_fresh(0.0, 0.3001, CFG)


def test_stale_frame_publishes_nothing():
    result = gate_frame([(1.0, 0.0, 0.5)], 100, 100, 0.0, 1.0, CFG)
    assert not result.accepted and result.reason == 'stale' and result.points == ()


def test_low_valid_ratio_is_dropped_not_published_as_empty():
    """A glass table returns almost no depth; that is unknown, not clear."""
    result = gate_frame([(1.0, 0.0, 0.5)], 1000, 100, 0.0, 0.0, CFG)
    assert not result.accepted and result.reason == 'low_valid_ratio'


def test_valid_ratio_boundary_is_inclusive():
    assert gate_frame([(1.0, 0.0, 0.5)], 1000, 300, 0.0, 0.0, CFG).accepted
    assert not gate_frame([(1.0, 0.0, 0.5)], 1000, 299, 0.0, 0.0, CFG).accepted


def test_valid_ratio_of_empty_frame_is_zero():
    assert valid_ratio(0, 0) == 0.0


def test_ground_points_are_removed():
    assert filter_points([(1.0, 0.0, 0.0), (1.0, 0.0, 0.03)], CFG) == []


def test_point_just_above_ground_tolerance_still_needs_min_height():
    # 0.04 m clears the ground band but is below obstacle_min_height_m.
    assert filter_points([(1.0, 0.0, 0.04)], CFG) == []
    assert filter_points([(1.0, 0.0, 0.05)], CFG) == [(1.0, 0.0, 0.05)]


def test_ceiling_points_are_removed():
    assert filter_points([(1.0, 0.0, 1.21)], CFG) == []
    assert filter_points([(1.0, 0.0, 1.2)], CFG) == [(1.0, 0.0, 1.2)]


def test_range_window_is_enforced():
    assert filter_points([(0.1, 0.0, 0.5)], CFG) == []
    assert filter_points([(5.0, 0.0, 0.5)], CFG) == []
    assert len(filter_points([(0.2, 0.0, 0.5), (4.0, 0.0, 0.5)], CFG)) == 2


def test_lateral_distance_counts_toward_range():
    # 3 m forward and 4 m sideways is 5 m away, past max_range_m.
    assert filter_points([(3.0, 4.0, 0.5)], CFG) == []


def test_accepted_frame_returns_only_surviving_points():
    points = [(1.0, 0.0, 0.5), (1.0, 0.0, 0.0), (10.0, 0.0, 0.5)]
    result = gate_frame(points, 100, 100, 0.0, 0.0, CFG)
    assert result.accepted and result.points == ((1.0, 0.0, 0.5),)
