"""Forward and inverse kinematics for the 6-axis arm.

The arm has the usual hobby-servo layout: a yawing base, a shoulder and elbow
that move the wrist in a vertical plane, and a wrist whose axes meet at a point.
That last property is what makes a closed-form solution possible — position is
decided by the first three joints alone.

Scope, stated plainly: this solves **position plus approach pitch plus tool
roll**, not arbitrary 6-DOF orientation. Joint 4 (forearm roll) is held at zero
and joint 6 carries the tool roll, so the gripper always approaches within the
vertical plane through the base yaw axis. That is exactly what the first version
needs — top-down and side grasps of fixed classes off a fixed work pose
(技术方案 §3.12.1) — and pretending to more would be a solver nobody has
validated against a real arm.

Link lengths come from config, not from this file: they are a property of the
arm that was bought, and until one is bought there is nothing to hard-code.
Correctness is checked by round-tripping IK through FK, which needs no hardware.

# @spec 家庭服务机器人技术方案.md#3.12.5
"""
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArmGeometry:
    """Measured lengths, in metres, along the arm's own chain.

    base_height:     arm_base_link up to the shoulder axis
    shoulder_offset: sideways offset of the shoulder from the base yaw axis
    upper_arm:       shoulder axis to elbow axis
    forearm:         elbow axis to wrist centre
    wrist_length:    wrist centre to tool0
    """
    base_height: float = 0.10
    shoulder_offset: float = 0.0
    upper_arm: float = 0.15
    forearm: float = 0.14
    wrist_length: float = 0.08

    def max_reach(self) -> float:
        return self.upper_arm + self.forearm

    def min_reach(self) -> float:
        return abs(self.upper_arm - self.forearm)


@dataclass(frozen=True)
class JointLimits:
    """Soft limits, per joint, in radians. Hard limits live in the controller."""
    lower: tuple = (-2.79, -1.57, -2.36, -2.79, -1.92, -3.14)
    upper: tuple = (2.79, 1.92, 2.36, 2.79, 1.92, 3.14)

    def contains(self, joints) -> bool:
        return all(lo <= j <= hi for j, lo, hi in zip(joints, self.lower, self.upper))

    def violations(self, joints):
        return tuple(i for i, (j, lo, hi) in enumerate(zip(joints, self.lower, self.upper))
                     if not lo <= j <= hi)


@dataclass(frozen=True)
class Unreachable(Exception):
    reason: str
    detail: str = ''

    def __str__(self):
        return f'{self.reason}{": " + self.detail if self.detail else ""}'


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def forward(joints, geometry: ArmGeometry):
    """tool0 position in arm_base_link, plus the approach pitch.

    Returns ((x, y, z), yaw, pitch) where pitch is the tool's inclination in the
    arm plane: 0 points straight out, -pi/2 points straight down.
    """
    if len(joints) != 6:
        raise ValueError(f'expected 6 joints, got {len(joints)}')
    j1, j2, j3, _, j5, _ = joints
    # Radius and height of the wrist centre within the vertical arm plane.
    planar = (geometry.shoulder_offset
              + geometry.upper_arm * math.cos(j2)
              + geometry.forearm * math.cos(j2 + j3))
    height = (geometry.base_height
              + geometry.upper_arm * math.sin(j2)
              + geometry.forearm * math.sin(j2 + j3))
    pitch = j2 + j3 + j5
    planar += geometry.wrist_length * math.cos(pitch)
    height += geometry.wrist_length * math.sin(pitch)
    return ((planar * math.cos(j1), planar * math.sin(j1), height), j1, pitch)


def inverse(position, pitch, geometry: ArmGeometry, limits: JointLimits,
            roll: float = 0.0, elbow_up: bool = True):
    """Joint angles that put tool0 at `position` with the tool at `pitch`.

    Raises Unreachable rather than returning a nearest-miss: an arm that goes
    "roughly there" is worse than one that refuses, because the gripper closes
    on nothing and the failure is discovered by looking at it.
    """
    x, y, z = position
    j1 = math.atan2(y, x)

    # Back the wrist offset out first, so the remaining problem is a plain 2R chain.
    planar = math.hypot(x, y) - geometry.shoulder_offset \
        - geometry.wrist_length * math.cos(pitch)
    height = z - geometry.base_height - geometry.wrist_length * math.sin(pitch)

    distance = math.hypot(planar, height)
    if distance > geometry.max_reach():
        raise Unreachable('out_of_reach',
                          f'{distance:.3f} m > {geometry.max_reach():.3f} m')
    if distance < geometry.min_reach():
        raise Unreachable('inside_minimum_reach',
                          f'{distance:.3f} m < {geometry.min_reach():.3f} m')
    if distance == 0.0:
        raise Unreachable('singular', 'wrist centre coincides with the shoulder')

    # Law of cosines on the shoulder-elbow-wrist triangle.
    cos_elbow = ((distance ** 2 - geometry.upper_arm ** 2 - geometry.forearm ** 2)
                 / (2.0 * geometry.upper_arm * geometry.forearm))
    cos_elbow = max(-1.0, min(1.0, cos_elbow))
    elbow = math.acos(cos_elbow)
    j3 = elbow if elbow_up else -elbow

    beta = math.atan2(height, planar)
    cos_alpha = ((distance ** 2 + geometry.upper_arm ** 2 - geometry.forearm ** 2)
                 / (2.0 * distance * geometry.upper_arm))
    cos_alpha = max(-1.0, min(1.0, cos_alpha))
    alpha = math.acos(cos_alpha)
    # Sign pairing matters: a positive elbow angle swings the forearm counter-
    # clockwise off the upper arm, which puts the wrist counter-clockwise of the
    # upper arm's own direction. So beta = j2 + alpha, i.e. j2 = beta - alpha.
    # Pairing these the other way round silently returns a mirrored pose that
    # still looks plausible until it is fed through FK.
    j2 = beta - alpha if elbow_up else beta + alpha

    # The wrist takes up whatever pitch the arm did not.
    j5 = wrap_angle(pitch - j2 - j3)
    joints = (wrap_angle(j1), wrap_angle(j2), wrap_angle(j3), 0.0, j5, wrap_angle(roll))

    bad = limits.violations(joints)
    if bad:
        raise Unreachable('joint_limit',
                          'joints ' + ', '.join(str(i + 1) for i in bad))
    return joints


def solve(position, pitch, geometry, limits, roll=0.0):
    """Prefer elbow-up; fall back to elbow-down before giving up.

    Elbow-up keeps the forearm above the working surface, which matters on a
    table: the elbow-down mirror of the same pose often sweeps through it.
    """
    first = None
    for elbow_up in (True, False):
        try:
            return inverse(position, pitch, geometry, limits, roll, elbow_up)
        except Unreachable as exc:
            first = first or exc
            if exc.reason in ('out_of_reach', 'inside_minimum_reach', 'singular'):
                raise
    raise first


def interpolate(start, end, steps: int):
    """A joint-space path. Straight lines in joint space, which is what the
    servo controller interpolates natively anyway."""
    if steps < 2:
        raise ValueError('steps must be at least 2')
    out = []
    for i in range(steps):
        t = i / (steps - 1)
        out.append(tuple(s + (e - s) * t for s, e in zip(start, end)))
    return out
