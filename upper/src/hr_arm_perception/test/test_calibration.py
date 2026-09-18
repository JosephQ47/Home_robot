"""ARM-6 and 技术方案 §3.12.3: an invalid hand-eye calibration must block grasping."""
import datetime
import json
import math
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_arm_perception.calibration import (CalibrationError, Transform, load)  # noqa: E402

GOOD = {
    'arm_serial': 'ARM-0001', 'camera_serial': 'D435I-9999',
    'created': '2026-09-01', 'valid_until': '2027-03-01',
    'software_version': '0.1.0',
    'tool0_to_camera': {'x': 0.05, 'y': 0.0, 'z': 0.03,
                        'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
    'mean_error_m': 0.004, 'max_error_m': 0.009,
}


def write(data):
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def test_loads_a_complete_file():
    c = load(write(GOOD))
    assert c.arm_serial == 'ARM-0001'
    assert c.tool0_to_camera.x == 0.05


def test_missing_file_is_refused():
    with pytest.raises(CalibrationError, match='not found'):
        load('/nonexistent/calib.json')


def test_every_required_field_is_required():
    for field in ('arm_serial', 'camera_serial', 'created', 'valid_until',
                  'software_version', 'tool0_to_camera'):
        data = dict(GOOD)
        data.pop(field)
        with pytest.raises(CalibrationError, match='missing'):
            load(write(data))


def test_malformed_json_is_refused():
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    f.write('{not json')
    f.close()
    with pytest.raises(CalibrationError, match='not valid JSON'):
        load(f.name)


def test_transform_needs_all_six_components():
    data = dict(GOOD, tool0_to_camera={'x': 0.0, 'y': 0.0, 'z': 0.0})
    with pytest.raises(CalibrationError, match='roll/pitch/yaw'):
        load(write(data))


def test_bad_dates_are_refused():
    with pytest.raises(CalibrationError, match='ISO dates'):
        load(write(dict(GOOD, valid_until='next march')))
    with pytest.raises(CalibrationError, match='precedes'):
        load(write(dict(GOOD, created='2027-01-01', valid_until='2026-01-01')))


def test_swapping_the_camera_invalidates_it():
    c = load(write(GOOD))
    with pytest.raises(CalibrationError, match='camera'):
        c.check('ARM-0001', 'D435I-0000', datetime.date(2026, 10, 1))


def test_swapping_the_arm_invalidates_it():
    c = load(write(GOOD))
    with pytest.raises(CalibrationError, match='arm'):
        c.check('ARM-0002', 'D435I-9999', datetime.date(2026, 10, 1))


def test_expiry_boundary_is_inclusive():
    c = load(write(GOOD))
    c.check('ARM-0001', 'D435I-9999', datetime.date(2027, 3, 1))     # last valid day
    with pytest.raises(CalibrationError, match='expired'):
        c.check('ARM-0001', 'D435I-9999', datetime.date(2027, 3, 2))


def test_identity_transform_moves_nothing():
    assert Transform().apply((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_translation_is_applied():
    assert Transform(x=0.1, y=-0.2, z=0.3).apply((0.0, 0.0, 0.0)) == \
        pytest.approx((0.1, -0.2, 0.3))


def test_yaw_rotates_about_z():
    out = Transform(yaw=math.pi / 2).apply((1.0, 0.0, 0.0))
    assert out == pytest.approx((0.0, 1.0, 0.0), abs=1e-9)


def test_rotation_then_translation_compose_in_that_order():
    out = Transform(x=1.0, yaw=math.pi / 2).apply((1.0, 0.0, 0.0))
    assert out == pytest.approx((1.0, 1.0, 0.0), abs=1e-9)
