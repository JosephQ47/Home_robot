"""Rules ARM-1..ARM-6 from docs/features/hr_arm.md."""
import itertools
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_arm_controller.grasp_state_machine import (ABORT_CONDITIONS, BaseState,  # noqa: E402
                                                   GraspInputs, GraspStateMachine,
                                                   LiftEvidence, State)

STOPPED = BaseState(nav_goal_finished=True, cmd_vel_zero=True,
                    wheel_speed_zero=True, remote_override=False)
GOOD_GRASP = GraspInputs(*(True,) * 7)
HOLDING = LiftEvidence(True, True, False)


def at(state, sm=None):
    """Drive a fresh machine to `state` through the happy path."""
    sm = sm or GraspStateMachine()
    sm.start()
    while sm.state is not state:
        sm.advance(STOPPED, GOOD_GRASP, HOLDING)
    return sm


def test_base_must_be_fully_stopped():
    """ARM-1: each of the four confirmations is individually necessary."""
    for i in range(4):
        flags = [True, True, True, False]
        flags[i] = not flags[i]
        base = BaseState(*flags)
        sm = at(State.BASE_STOP_CONFIRM)
        sm.advance(base, GOOD_GRASP, HOLDING)
        assert sm.state is State.ABORTED
        assert sm.abort_reason == 'base_not_stopped'


def test_fully_stopped_base_proceeds():
    sm = at(State.BASE_STOP_CONFIRM)
    assert sm.advance(STOPPED, GOOD_GRASP, HOLDING) is State.D435I_PRECHECK


def test_every_grasp_precondition_is_necessary():
    """ARM-2: flipping any single one of the seven checks blocks the grasp."""
    for i in range(7):
        flags = [True] * 7
        flags[i] = False
        sm = at(State.SELECT_GRASP)
        sm.advance(STOPPED, GraspInputs(*flags), HOLDING)
        assert sm.state is State.ABORTED, f'precondition {i} did not block'
        assert sm.abort_reason == 'grasp_candidate_rejected'


def test_closed_gripper_alone_is_not_success():
    """ARM-3: one signal is never enough."""
    for combo in itertools.combinations(range(3), 1):
        flags = [False, False, False]
        for i in combo:
            flags[i] = True
        sm = at(State.LIFT_VERIFY)
        sm.advance(STOPPED, GOOD_GRASP, LiftEvidence(*flags))
        assert sm.state is State.ABORTED
        assert sm.abort_reason == 'grasp_not_confirmed'


def test_two_agreeing_signals_confirm_the_hold():
    for combo in itertools.combinations(range(3), 2):
        flags = [False, False, False]
        for i in combo:
            flags[i] = True
        sm = at(State.LIFT_VERIFY)
        assert sm.advance(STOPPED, GOOD_GRASP, LiftEvidence(*flags)) is State.PLACE


def test_every_abort_condition_stops_from_every_stage():
    """ARM-4: no stage is exempt, and the failed stage is always recorded."""
    for stage in (State.ARM_HOME, State.D435I_PRECHECK, State.APPROACH, State.PLACE):
        for reason in ABORT_CONDITIONS:
            sm = at(stage)
            assert sm.check_faults(**{reason: True}) is True
            assert sm.state is State.ABORTED
            assert sm.failed_stage is stage
            assert sm.abort_reason == reason
            assert sm.base_motion_allowed is False


def test_base_motion_is_refused_for_the_whole_task():
    sm = GraspStateMachine()
    assert sm.request_base_motion() is True
    sm.start()
    for stage in (State.ARM_HOME, State.APPROACH, State.PLACE):
        sm = at(stage)
        assert sm.request_base_motion() is False


def test_base_motion_returns_after_a_clean_finish():
    sm = at(State.RELEASE)
    assert sm.advance(STOPPED, GOOD_GRASP, HOLDING) is State.IDLE
    assert sm.request_base_motion() is True


def test_no_automatic_retry():
    """ARM-5"""
    sm = at(State.APPROACH)
    sm.abort('servo_fault')
    with pytest.raises(RuntimeError, match='new task'):
        sm.retry()


def test_aborted_machine_does_not_advance():
    sm = at(State.APPROACH)
    sm.abort('estop')
    assert sm.advance(STOPPED, GOOD_GRASP, HOLDING) is State.ABORTED


def test_cannot_start_twice():
    sm = GraspStateMachine()
    sm.start()
    with pytest.raises(RuntimeError, match='already running'):
        sm.start()


def test_clean_run_walks_the_documented_sequence():
    sm = GraspStateMachine()
    sm.start()
    visited = [sm.state]
    while sm.state is not State.IDLE:
        visited.append(sm.advance(STOPPED, GOOD_GRASP, HOLDING))
    assert visited[:-1] == [State.ARM_HOME, State.NAVIGATE_TO_WORKPOSE, State.BASE_STOP_CONFIRM,
                            State.D435I_PRECHECK, State.DETECT_TARGET, State.SELECT_GRASP,
                            State.PREGRASP, State.APPROACH, State.CLOSE_GRIPPER,
                            State.LIFT_VERIFY, State.PLACE, State.RELEASE]
