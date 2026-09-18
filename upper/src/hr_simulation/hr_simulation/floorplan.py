"""Turn a floor-plan description into wall segments, and cast rays at them.

Pure geometry with no ROS in it, so the ray caster can be tested directly —
a laser simulator that is subtly wrong produces a map that is subtly wrong,
and that is very hard to notice later.

# @spec 家庭服务机器人技术方案.md#3.3
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float


def _split(a: float, b: float, gaps):
    """Return the parts of [a, b] left once each gap is removed."""
    parts = [(a, b)]
    for g0, g1 in sorted(gaps or []):
        out = []
        for s, e in parts:
            if g1 <= s or g0 >= e:
                out.append((s, e))
                continue
            if s < g0:
                out.append((s, g0))
            if g1 < e:
                out.append((g1, e))
        parts = out
    return [(s, e) for s, e in parts if e - s > 1e-9]


def rectangle(x_min, y_min, x_max, y_max):
    return [Segment(x_min, y_min, x_max, y_min), Segment(x_max, y_min, x_max, y_max),
            Segment(x_max, y_max, x_min, y_max), Segment(x_min, y_max, x_min, y_min)]


def build(plan):
    """Expand a floor-plan mapping into the list of wall segments."""
    o = plan['outer']
    segments = rectangle(o['x_min'], o['y_min'], o['x_max'], o['y_max'])
    for wall in plan.get('walls', []) or []:
        for s, e in _split(wall['from'], wall['to'], wall.get('gaps')):
            if wall['axis'] == 'y':          # a wall running along x, at a fixed y
                segments.append(Segment(s, wall['at'], e, wall['at']))
            elif wall['axis'] == 'x':        # a wall running along y, at a fixed x
                segments.append(Segment(wall['at'], s, wall['at'], e))
            else:
                raise ValueError(f"wall axis must be x or y, got {wall['axis']!r}")
    for b in plan.get('boxes', []) or []:
        segments += rectangle(b['x_min'], b['y_min'], b['x_max'], b['y_max'])
    return segments


def ray_hit(ox, oy, angle, segments, max_range):
    """Distance from (ox, oy) along `angle` to the nearest segment.

    Returns max_range when nothing is hit, which is what a real scanner reports
    for an out-of-range return.
    """
    dx, dy = math.cos(angle), math.sin(angle)
    best = max_range
    for s in segments:
        sx, sy = s.x2 - s.x1, s.y2 - s.y1
        denom = dx * sy - dy * sx
        if abs(denom) < 1e-12:
            continue                      # parallel; a grazing hit carries no information
        # Solve  origin + t*d  ==  s.p1 + u*s  for t along the ray and u along the wall.
        t = ((s.x1 - ox) * sy - (s.y1 - oy) * sx) / denom
        u = ((s.x1 - ox) * dy - (s.y1 - oy) * dx) / denom
        if t >= 0.0 and 0.0 <= u <= 1.0 and t < best:
            best = t
    return best


def scan(pose, segments, angle_min, angle_max, increment, max_range):
    """A full sweep from `pose` (x, y, yaw), in the sensor's own frame order."""
    x, y, yaw = pose
    count = int(round((angle_max - angle_min) / increment)) + 1
    return [ray_hit(x, y, yaw + angle_min + i * increment, segments, max_range)
            for i in range(count)]
