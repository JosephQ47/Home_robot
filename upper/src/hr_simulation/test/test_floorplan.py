"""Geometry for the planar simulator. A wrong ray caster makes a wrong map."""
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_simulation.floorplan import (Segment, build, ray_hit, rectangle,  # noqa: E402
                                     scan, _split)

ROOM = rectangle(0.0, 0.0, 10.0, 10.0)


def test_split_removes_a_middle_gap():
    assert _split(0.0, 10.0, [[4.0, 6.0]]) == [(0.0, 4.0), (6.0, 10.0)]


def test_split_handles_no_gaps_and_edge_gaps():
    assert _split(0.0, 10.0, None) == [(0.0, 10.0)]
    assert _split(0.0, 10.0, [[0.0, 3.0]]) == [(3.0, 10.0)]
    assert _split(0.0, 10.0, [[7.0, 10.0]]) == [(0.0, 7.0)]


def test_split_with_several_gaps():
    assert _split(0.0, 10.0, [[7.0, 8.0], [2.0, 3.0]]) == [(0.0, 2.0), (3.0, 7.0), (8.0, 10.0)]


def test_a_gap_covering_everything_leaves_nothing():
    assert _split(2.0, 4.0, [[0.0, 9.0]]) == []


def test_rectangle_is_closed():
    r = rectangle(0, 0, 2, 3)
    assert len(r) == 4
    assert (r[-1].x2, r[-1].y2) == (r[0].x1, r[0].y1)


def test_ray_hits_the_wall_straight_ahead():
    assert ray_hit(5.0, 5.0, 0.0, ROOM, 20.0) == pytest.approx(5.0)
    assert ray_hit(5.0, 5.0, math.pi, ROOM, 20.0) == pytest.approx(5.0)
    assert ray_hit(5.0, 5.0, math.pi / 2, ROOM, 20.0) == pytest.approx(5.0)


def test_ray_reports_the_nearest_of_several_walls():
    assert ray_hit(2.0, 5.0, 0.0, ROOM, 20.0) == pytest.approx(8.0)
    assert ray_hit(2.0, 5.0, math.pi, ROOM, 20.0) == pytest.approx(2.0)


def test_diagonal_ray_uses_real_distance():
    assert ray_hit(5.0, 5.0, math.pi / 4, ROOM, 20.0) == pytest.approx(5.0 * math.sqrt(2))


def test_a_ray_that_hits_nothing_returns_max_range():
    wall = [Segment(0.0, 5.0, 1.0, 5.0)]
    assert ray_hit(5.0, 0.0, 0.0, wall, 12.0) == 12.0


def test_a_ray_never_reports_a_hit_behind_itself():
    """t < 0 is a wall the beam is travelling away from."""
    wall = [Segment(-5.0, -1.0, -5.0, 1.0)]
    assert ray_hit(0.0, 0.0, 0.0, wall, 12.0) == 12.0


def test_a_ray_parallel_to_a_wall_does_not_hit_it():
    wall = [Segment(0.0, 1.0, 10.0, 1.0)]
    assert ray_hit(0.0, 0.0, 0.0, wall, 12.0) == 12.0


def test_a_ray_misses_a_segment_it_passes_beyond_the_end_of():
    wall = [Segment(4.0, 4.0, 4.0, 4.5)]      # short stub, well above the beam
    assert ray_hit(0.0, 0.0, 0.0, wall, 12.0) == 12.0


def test_doors_are_actually_open():
    plan = {'outer': {'x_min': 0, 'y_min': 0, 'x_max': 10, 'y_max': 10},
            'walls': [{'axis': 'y', 'at': 5.0, 'from': 0.0, 'to': 10.0,
                       'gaps': [[4.0, 6.0]]}]}
    segs = build(plan)
    # Straight up through the doorway reaches the far outer wall.
    assert ray_hit(5.0, 1.0, math.pi / 2, segs, 20.0) == pytest.approx(9.0)
    # Straight up beside it stops at the interior wall.
    assert ray_hit(1.0, 1.0, math.pi / 2, segs, 20.0) == pytest.approx(4.0)


def test_build_includes_outer_walls_and_furniture():
    plan = {'outer': {'x_min': 0, 'y_min': 0, 'x_max': 10, 'y_max': 10},
            'boxes': [{'x_min': 2, 'y_min': 2, 'x_max': 3, 'y_max': 3}]}
    assert len(build(plan)) == 8


def test_unknown_axis_is_rejected():
    plan = {'outer': {'x_min': 0, 'y_min': 0, 'x_max': 1, 'y_max': 1},
            'walls': [{'axis': 'z', 'at': 0.5, 'from': 0.0, 'to': 1.0}]}
    with pytest.raises(ValueError, match='axis'):
        build(plan)


def test_scan_length_and_orientation():
    ranges = scan((5.0, 5.0, 0.0), ROOM, -math.pi, math.pi, math.pi / 180, 20.0)
    assert len(ranges) == 361
    assert ranges[180] == pytest.approx(5.0)        # dead ahead
    assert ranges[0] == pytest.approx(5.0)          # directly behind


def test_scan_rotates_with_the_robot():
    """Turning the robot must move the features, not the array."""
    a = scan((2.0, 5.0, 0.0), ROOM, -math.pi, math.pi, math.pi / 2, 20.0)
    b = scan((2.0, 5.0, math.pi), ROOM, -math.pi, math.pi, math.pi / 2, 20.0)
    assert a[2] == pytest.approx(8.0)               # facing +x, far wall
    assert b[2] == pytest.approx(2.0)               # turned around, near wall


def test_the_shipped_floorplan_is_enclosed_and_navigable():
    import yaml
    cfg = pathlib.Path(__file__).resolve().parents[1] / 'config' / 'home_floorplan.yaml'
    plan = yaml.safe_load(cfg.read_text())['floorplan']
    segs = build(plan)
    start = plan['start']
    # From the start pose every direction eventually meets a wall: the plan has
    # no leak to infinity, which would make the map unbounded.
    for i in range(72):
        r = ray_hit(start['x'], start['y'], i * math.pi / 36, segs, 50.0)
        assert r < 50.0, f'ray {i} escaped the floor plan'
    # And the robot is not standing inside a wall or a piece of furniture.
    assert min(ray_hit(start['x'], start['y'], i * math.pi / 36, segs, 50.0)
               for i in range(72)) > 0.3


def test_scan_from_every_reachable_pose_stays_inside_the_plan():
    """No ray may escape the shipped floor plan.

    A leaking plan paints free space through walls and quietly ruins the map,
    so this sweeps the whole interior rather than only the start pose.
    """
    import yaml
    cfg = pathlib.Path(__file__).resolve().parents[1] / 'config' / 'home_floorplan.yaml'
    plan = yaml.safe_load(cfg.read_text())['floorplan']
    segs = build(plan)
    checked = 0
    for gx in [x * 0.4 for x in range(1, 17)]:
        for gy in [y * 0.4 for y in range(1, 19)]:
            clearance = min(ray_hit(gx, gy, i * math.pi / 12, segs, 60.0) for i in range(24))
            if clearance > 59.0 or clearance < 0.15:
                continue                       # outside the plan, or inside furniture
            checked += 1
            escaped = [i for i in range(72)
                       if ray_hit(gx, gy, i * math.pi / 36, segs, 40.0) >= 40.0]
            assert not escaped, f'rays escaped from ({gx:.1f}, {gy:.1f}): {escaped[:4]}'
    assert checked > 100, 'the sweep did not actually reach inside the plan'


def test_point_segment_distance_handles_ends_and_middle():
    from hr_simulation.floorplan import point_segment_distance
    wall = Segment(0.0, 0.0, 10.0, 0.0)
    assert point_segment_distance(5.0, 3.0, wall) == pytest.approx(3.0)   # beside it
    assert point_segment_distance(-4.0, 0.0, wall) == pytest.approx(4.0)  # past the start
    assert point_segment_distance(14.0, 0.0, wall) == pytest.approx(4.0)  # past the end
    assert point_segment_distance(3.0, 0.0, wall) == pytest.approx(0.0)   # on it


def test_blocked_refuses_a_body_overlapping_a_wall():
    from hr_simulation.floorplan import blocked
    assert blocked(0.1, 5.0, ROOM, 0.25)        # 0.1 m from the wall, radius 0.25
    assert not blocked(5.0, 5.0, ROOM, 0.25)    # middle of the room


def test_a_doorway_is_too_narrow_for_an_oversized_body():
    from hr_simulation.floorplan import blocked
    plan = {'outer': {'x_min': 0, 'y_min': 0, 'x_max': 10, 'y_max': 10},
            'walls': [{'axis': 'y', 'at': 5.0, 'from': 0.0, 'to': 10.0,
                       'gaps': [[4.6, 5.4]]}]}       # a 0.8 m door
    segs = build(plan)
    assert not blocked(5.0, 5.0, segs, 0.35)     # a 0.7 m body fits
    assert blocked(5.0, 5.0, segs, 0.45)         # a 0.9 m body does not
