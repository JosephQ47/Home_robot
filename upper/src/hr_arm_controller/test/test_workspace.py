"""The shipped configuration must describe an arm that can reach its own targets.

Link lengths and the grasp envelope are separate parameters, so nothing stops
them from disagreeing — and when they do, the failure is an IK refusal in the
middle of a real grasp rather than anything at startup. These tests read the
installed YAML and check the two against each other.
"""
import math
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_arm_controller.kinematics import (ArmGeometry, JointLimits, Unreachable,  # noqa: E402
                                          solve)

CONFIG = pathlib.Path(__file__).resolve().parents[1] / 'config' / 'arm_controller.yaml'


@pytest.fixture(scope='module')
def params():
    return yaml.safe_load(CONFIG.read_text())['hr_arm_controller']['ros__parameters']


@pytest.fixture(scope='module')
def geometry(params):
    return ArmGeometry(base_height=params['base_height_m'],
                       shoulder_offset=params['shoulder_offset_m'],
                       upper_arm=params['upper_arm_m'],
                       forearm=params['forearm_m'],
                       wrist_length=params['wrist_length_m'])


@pytest.fixture(scope='module')
def limits(params):
    return JointLimits(lower=tuple(params['joint_lower_rad']),
                       upper=tuple(params['joint_upper_rad']))


def test_every_link_length_is_positive(geometry):
    assert geometry.upper_arm > 0 and geometry.forearm > 0 and geometry.wrist_length > 0
    assert geometry.base_height > 0


def test_limits_are_ordered_and_six_long(params):
    lower, upper = params['joint_lower_rad'], params['joint_upper_rad']
    assert len(lower) == len(upper) == 6
    assert all(lo < hi for lo, hi in zip(lower, upper))


def test_configured_place_position_is_reachable(params, geometry, limits):
    """The bug this test exists for: a drop-off point outside the arm's reach."""
    place = tuple(params['place_position_xyz'])
    solve(place, params['approach_pitch_rad'], geometry, limits)


def test_place_position_is_reachable_with_the_lift_clearance(params, geometry, limits):
    """The arm arrives at the drop-off holding the object above the surface."""
    x, y, z = params['place_position_xyz']
    solve((x, y, z + params['lift_height_m']), params['approach_pitch_rad'],
          geometry, limits)


def test_a_representative_grasp_envelope_is_reachable(params, geometry, limits):
    """Grasp, pre-grasp and lift for an object on the work surface in front."""
    pitch = params['approach_pitch_rad']
    target = (0.24, 0.03, 0.04)
    for label, z in (('grasp', target[2]),
                     ('pregrasp', target[2] + params['pregrasp_height_m']),
                     ('lift', target[2] + params['lift_height_m'])):
        try:
            solve((target[0], target[1], z), pitch, geometry, limits)
        except Unreachable as exc:
            pytest.fail(f'{label} at z={z:.3f} is unreachable: {exc}')


def test_pregrasp_clearance_fits_inside_the_reach(params, geometry):
    """Raising the target eats reach; the config must leave room for that."""
    lift = max(params['pregrasp_height_m'], params['lift_height_m'])
    assert lift < geometry.max_reach(), \
        'the pre-grasp clearance alone exceeds the arm reach'


def test_gripper_opening_is_positive_and_ordered(params):
    assert params['gripper_open_m'] > params['gripper_closed_margin_m'] > 0


def test_approach_pitch_points_downward(params):
    """The first version grasps off a flat surface."""
    assert params['approach_pitch_rad'] == pytest.approx(-math.pi / 2, abs=0.02)


def test_a_target_beyond_reach_is_still_refused(geometry, limits):
    """The envelope checks above must not be passing because nothing is checked."""
    with pytest.raises(Unreachable):
        solve((geometry.max_reach() + geometry.wrist_length + 0.20, 0.0, 0.05),
              -math.pi / 2, geometry, limits)


def test_accepted_classes_and_places_are_not_empty(params):
    assert [c for c in params['accepted_object_classes'] if c]
    assert [p for p in params['accepted_places'] if p]
