"""Hand-eye calibration: loading it, checking it is still valid, and using it.

`tool0 -> d435i_link` must come from a calibration run, never from a tape
measure (技术方案 §3.12.3). The file therefore carries the serials and the date
it was produced for, and this module refuses it the moment any of that stops
matching the robot it is loaded on.

# @spec 家庭服务机器人技术方案.md#3.12.3
"""
import datetime
import json
import math
import pathlib
from dataclasses import dataclass, field

REQUIRED_FIELDS = ('arm_serial', 'camera_serial', 'created', 'valid_until',
                   'software_version', 'tool0_to_camera')


@dataclass(frozen=True)
class Transform:
    """A rigid transform as translation + RPY, which is what a calibration emits."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def matrix(self):
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        return (
            (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, self.x),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, self.y),
            (-sp,     cp * sr,                cp * cr,                self.z),
            (0.0,     0.0,                    0.0,                    1.0),
        )

    def apply(self, point):
        m = self.matrix()
        x, y, z = point
        return tuple(m[r][0] * x + m[r][1] * y + m[r][2] * z + m[r][3] for r in range(3))


@dataclass(frozen=True)
class CalibrationError(Exception):
    reason: str

    def __str__(self):
        return self.reason


@dataclass
class HandEyeCalibration:
    arm_serial: str
    camera_serial: str
    created: datetime.date
    valid_until: datetime.date
    software_version: str
    tool0_to_camera: Transform
    mean_error_m: float = 0.0
    max_error_m: float = 0.0
    source: str = ''

    def check(self, arm_serial: str, camera_serial: str, today: datetime.date) -> None:
        """Raise unless this calibration still describes *this* robot, today.

        Swapping the camera, the end effector, a servo zero or the mounting
        position invalidates it, and an invalid calibration must block grasping
        rather than silently shift every grasp by its error.
        """
        if arm_serial and self.arm_serial != arm_serial:
            raise CalibrationError(
                f'calibration is for arm {self.arm_serial}, not {arm_serial}')
        if camera_serial and self.camera_serial != camera_serial:
            raise CalibrationError(
                f'calibration is for camera {self.camera_serial}, not {camera_serial}')
        if today > self.valid_until:
            raise CalibrationError(
                f'calibration expired on {self.valid_until.isoformat()}')


def load(path) -> HandEyeCalibration:
    """Read a calibration file, rejecting anything incomplete or malformed."""
    path = pathlib.Path(path)
    if not path.is_file():
        raise CalibrationError(f'calibration file not found: {path}')
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CalibrationError(f'calibration file is not valid JSON: {exc}') from exc
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise CalibrationError(f'calibration file is missing {", ".join(missing)}')
    try:
        created = datetime.date.fromisoformat(str(data['created']))
        valid_until = datetime.date.fromisoformat(str(data['valid_until']))
    except ValueError as exc:
        raise CalibrationError(f'calibration dates are not ISO dates: {exc}') from exc
    if valid_until < created:
        raise CalibrationError('calibration valid_until precedes created')
    t = data['tool0_to_camera']
    try:
        transform = Transform(*(float(t[k]) for k in ('x', 'y', 'z', 'roll', 'pitch', 'yaw')))
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationError(
            f'tool0_to_camera needs x/y/z/roll/pitch/yaw: {exc}') from exc
    return HandEyeCalibration(
        arm_serial=str(data['arm_serial']), camera_serial=str(data['camera_serial']),
        created=created, valid_until=valid_until,
        software_version=str(data['software_version']), tool0_to_camera=transform,
        mean_error_m=float(data.get('mean_error_m', 0.0)),
        max_error_m=float(data.get('max_error_m', 0.0)), source=str(path))
