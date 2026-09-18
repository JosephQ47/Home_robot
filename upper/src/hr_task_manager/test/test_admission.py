"""Task admission and arm precheck: 技术方案 §3.1.3、§3.12.2."""
import pytest

from hr_interfaces.msg import RobotStatus
from hr_task_manager.state_machine import (ARM_TASKS, SOURCES, admission_reason,
                                           arm_precheck_reason, is_arm_task)


def valid_status():
    s = RobotStatus()
    s.stm32_link_ok = True
    s.command_fresh = True
    s.wheel_odom_valid = True
    s.imu_valid = True
    s.safety_permit = True
    s.watchdog_healthy = True
    return s


def test_every_documented_source_is_admissible():
    for source in SOURCES:
        assert admission_reason(source, 'search', busy=False) == '', source


def test_voice_is_an_accepted_source():
    assert 'VOICE' in SOURCES
    assert admission_reason('VOICE', 'search', busy=False) == ''


def test_unknown_source_is_refused():
    for bogus in ('', 'ADMIN', 'voice', 'SYSTEM'):
        assert admission_reason(bogus, 'search', busy=False) == 'UNKNOWN_SOURCE'


def test_busy_refuses_ordinary_tasks_from_every_source():
    for source in SOURCES:
        assert admission_reason(source, 'search', busy=True) == 'TASK_BUSY', source


def test_arm_stop_is_admissible_while_busy():
    """A stop that queues behind the thing it is stopping is not a stop."""
    for source in SOURCES:
        assert admission_reason(source, 'ARM_STOP', busy=True) == '', source


def test_ordinary_tasks_cannot_preempt_a_critical_recharge():
    for source in ('SCHEDULE', 'WEB', 'VOICE'):
        assert admission_reason(source, 'search', busy=False,
                                battery_recharging=True) == 'BATTERY_RECHARGE_ACTIVE'


def test_the_recharge_itself_is_not_blocked_by_itself():
    assert admission_reason('SYSTEM_BATTERY', 'dock', busy=False,
                            battery_recharging=True) == ''


def test_arm_stop_survives_a_critical_recharge_too():
    assert admission_reason('VOICE', 'ARM_STOP', busy=True, battery_recharging=True) == ''


def test_arm_task_classification():
    for t in ('ARM_HOME', 'ARM_GRASP', 'ARM_RELEASE', 'ARM_STOP'):
        assert is_arm_task(t)
    for t in ('search', 'patrol', 'dock', 'navigate', '', 'arm_grasp'):
        assert not is_arm_task(t)
    assert ARM_TASKS == {'ARM_HOME', 'ARM_GRASP', 'ARM_RELEASE', 'ARM_STOP'}


def test_arm_precheck_accepts_a_settled_safe_robot():
    assert arm_precheck_reason(True, valid_status(), arm_ready=True, base_stopped=True) == ''


def test_arm_precheck_rejects_a_moving_base():
    assert arm_precheck_reason(True, valid_status(), arm_ready=True,
                               base_stopped=False) == 'BASE_NOT_STOPPED'


def test_arm_precheck_rejects_manual_takeover_and_safety_faults():
    s = valid_status(); s.remote_override = True
    assert arm_precheck_reason(True, s, True, True) == 'REMOTE_OVERRIDE'
    s = valid_status(); s.safety_permit = False
    assert arm_precheck_reason(True, s, True, True) == 'SAFETY_NOT_PERMITTED'
    s = valid_status(); s.fault_code = 7
    assert arm_precheck_reason(True, s, True, True) == 'SAFETY_NOT_PERMITTED'
    s = valid_status(); s.watchdog_healthy = False
    assert arm_precheck_reason(True, s, True, True) == 'WATCHDOG_UNHEALTHY'


def test_arm_precheck_rejects_stale_or_missing_status():
    assert arm_precheck_reason(False, valid_status(), True, True) == 'STM32_STATUS_UNAVAILABLE'
    assert arm_precheck_reason(True, None, True, True) == 'STM32_STATUS_UNAVAILABLE'


def test_arm_precheck_rejects_an_absent_arm():
    assert arm_precheck_reason(True, valid_status(), arm_ready=False,
                               base_stopped=True) == 'ARM_UNAVAILABLE'


def test_arm_precheck_does_not_require_navigation_or_localisation():
    """An arm task uses neither, so a missing map must not block a safe grasp."""
    s = valid_status()
    s.wheel_odom_valid = False
    s.imu_valid = False
    assert arm_precheck_reason(True, s, arm_ready=True, base_stopped=True) == ''
