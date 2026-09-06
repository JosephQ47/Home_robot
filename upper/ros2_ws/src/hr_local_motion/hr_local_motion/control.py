"""Pure bounded-control helpers."""
import math


def clamp(value, limit):
    return max(-limit, min(limit, value))


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def goal_command(x, y, yaw, gx, gy, max_linear, max_angular,
                 position_tolerance=0.08, heading_tolerance=0.15):
    dx, dy = gx - x, gy - y
    distance = math.hypot(dx, dy)
    if distance <= position_tolerance:
        return 0.0, 0.0, True
    error = wrap(math.atan2(dy, dx) - yaw)
    angular = clamp(1.2 * error, max_angular)
    if abs(error) > heading_tolerance:
        return 0.0, angular, False
    return min(max_linear, 0.6 * distance), angular, False


def follow_command(range_m, bearing_rad, desired_distance, minimum_distance,
                   max_linear, max_angular):
    if not all(math.isfinite(v) for v in (range_m, bearing_rad)):
        return 0.0, 0.0
    angular = clamp(1.2 * bearing_rad, max_angular)
    if range_m <= minimum_distance:
        return 0.0, angular
    linear = clamp(0.5 * (range_m - desired_distance), max_linear)
    return max(0.0, linear), angular
