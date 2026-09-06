import pytest

from hr_interfaces.msg import RobotStatus
from hr_task_manager.state_machine import TaskState, precheck_reason


def test_terminal_state_cannot_restart():
    state = TaskState('t1')
    state.transition('COMPLETED', 'DONE', 'done')
    with pytest.raises(ValueError):
        state.transition('RUNNING', 'NAVIGATING', 'bad')


def valid_status():
    status = RobotStatus()
    status.stm32_link_ok = True
    status.command_fresh = True
    status.wheel_odom_valid = True
    status.imu_valid = True
    status.safety_permit = True
    status.watchdog_healthy = True
    return status


def test_precheck_accepts_complete_safe_status():
    assert precheck_reason(True, True, valid_status(), True) == ''


def test_precheck_rejects_stale_command_and_watchdog():
    status = valid_status()
    status.command_fresh = False
    assert precheck_reason(True, True, status, True) == 'COMMAND_NOT_FRESH'
    status.command_fresh = True
    status.watchdog_healthy = False
    assert precheck_reason(True, True, status, True) == 'WATCHDOG_UNHEALTHY'
