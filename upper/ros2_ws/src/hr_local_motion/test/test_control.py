import math
from hr_local_motion.control import follow_command, goal_command


def test_goal_rotates_before_driving_and_stops_at_goal():
    linear, angular, done = goal_command(0, 0, 0, 0, 1, .1, .3)
    assert linear == 0 and angular > 0 and not done
    assert goal_command(0, 0, 0, .01, 0, .1, .3) == (0.0, 0.0, True)


def test_follow_is_bounded_and_invalid_input_stops():
    linear, angular = follow_command(3.0, 1.0, 1.2, .5, .1, .3)
    assert linear == .1 and angular == .3
    assert follow_command(math.nan, 0, 1.2, .5, .1, .3) == (0.0, 0.0)
    assert follow_command(.3, 0, 1.2, .5, .1, .3)[0] == 0
