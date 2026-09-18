"""The fixed-target grasp sequence and its safety interlocks.

First version is deliberately narrow (技术方案 §3.12.1): navigate to an accepted
work pose, stop the base, recognise one of a fixed set of classes with the
wrist D435i, grasp slowly, place at a fixed spot, go home. No grasping while
moving, no dynamic targets, no arbitrary objects.

Pure Python: no rclpy, no hardware. The arm and its servo controller do not
exist yet, so what is testable today is exactly the part that must never be
wrong — the interlocks.

# @spec 家庭服务机器人技术方案.md#3.12
"""
from dataclasses import dataclass, field
from enum import Enum


class State(Enum):
    IDLE = 'IDLE'
    ARM_HOME = 'ARM_HOME'
    NAVIGATE_TO_WORKPOSE = 'NAVIGATE_TO_WORKPOSE'
    BASE_STOP_CONFIRM = 'BASE_STOP_CONFIRM'
    D435I_PRECHECK = 'D435I_PRECHECK'
    DETECT_TARGET = 'DETECT_TARGET'
    SELECT_GRASP = 'SELECT_GRASP'
    PREGRASP = 'PREGRASP'
    APPROACH = 'APPROACH'
    CLOSE_GRIPPER = 'CLOSE_GRIPPER'
    LIFT_VERIFY = 'LIFT_VERIFY'
    PLACE = 'PLACE'
    RELEASE = 'RELEASE'
    ABORTED = 'ABORTED'


SEQUENCE = [State.ARM_HOME, State.NAVIGATE_TO_WORKPOSE, State.BASE_STOP_CONFIRM,
            State.D435I_PRECHECK, State.DETECT_TARGET, State.SELECT_GRASP, State.PREGRASP,
            State.APPROACH, State.CLOSE_GRIPPER, State.LIFT_VERIFY, State.PLACE, State.RELEASE]

# Conditions that abort from any state, at any time. Order matters only for the
# recorded reason; any one of them is sufficient.
ABORT_CONDITIONS = ('estop', 'remote_override', 'safety_fault', 'servo_fault',
                    'camera_fault', 'ik_failure', 'collision_predicted',
                    'target_lost', 'stage_timeout', 'cancelled')


@dataclass
class BaseState:
    """What the chassis reports. All four must be settled before the arm moves."""
    nav_goal_finished: bool = False
    cmd_vel_zero: bool = False
    wheel_speed_zero: bool = False
    remote_override: bool = False

    def stopped(self) -> bool:
        # ARM-1: four independent confirmations, not one optimistic flag.
        return (self.nav_goal_finished and self.cmd_vel_zero
                and self.wheel_speed_zero and not self.remote_override)


@dataclass
class GraspInputs:
    """Everything SELECT_GRASP must agree on before a joint trajectory exists."""
    detection_confident: bool = False
    depth_valid: bool = False
    hand_eye_calibration_valid: bool = False
    within_workspace: bool = False
    within_joint_limits: bool = False
    gripper_opening_ok: bool = False
    collision_free: bool = False

    def acceptable(self) -> bool:
        # ARM-2: every one of them, every time.
        return all((self.detection_confident, self.depth_valid,
                    self.hand_eye_calibration_valid, self.within_workspace,
                    self.within_joint_limits, self.gripper_opening_ok,
                    self.collision_free))


@dataclass
class LiftEvidence:
    """ARM-3: a closed gripper proves nothing on its own."""
    gripper_position_indicates_object: bool = False
    gripper_current_indicates_load: bool = False
    object_still_visible: bool = False

    def holding(self) -> bool:
        # At least two independent signals must agree.
        return sum((self.gripper_position_indicates_object,
                    self.gripper_current_indicates_load,
                    self.object_still_visible)) >= 2


@dataclass
class GraspStateMachine:
    state: State = State.IDLE
    failed_stage: State | None = None
    abort_reason: str | None = None
    base_motion_allowed: bool = True
    diagnostics: list = field(default_factory=list)

    def start(self) -> None:
        if self.state is not State.IDLE:
            raise RuntimeError('a grasp task is already running')
        self.state = State.ARM_HOME
        self.failed_stage = None
        self.abort_reason = None
        # ARM-4: the base loses its movement permit for the whole task.
        self.base_motion_allowed = False

    def abort(self, reason: str) -> None:
        """Stop the trajectory, revoke base motion, record where it broke."""
        if self.state in (State.IDLE, State.ABORTED):
            return
        self.failed_stage = self.state
        self.abort_reason = reason
        self.state = State.ABORTED
        self.base_motion_allowed = False
        self.diagnostics.append((self.failed_stage.value, reason))

    def check_faults(self, **faults) -> bool:
        """Apply the abort conditions. Returns True when it aborted."""
        for name in ABORT_CONDITIONS:
            if faults.get(name):
                self.abort(name)
                return True
        return False

    def request_base_motion(self) -> bool:
        """ARM-4: any base-move request during an arm task is refused."""
        return self.base_motion_allowed

    def advance(self, base: BaseState | None = None, grasp: GraspInputs | None = None,
                lift: LiftEvidence | None = None) -> State:
        """Move one step along SEQUENCE if this stage's guard is satisfied."""
        if self.state in (State.IDLE, State.ABORTED):
            return self.state
        if self.state is State.BASE_STOP_CONFIRM and not (base and base.stopped()):
            self.abort('base_not_stopped')
            return self.state
        if self.state is State.SELECT_GRASP and not (grasp and grasp.acceptable()):
            self.abort('grasp_candidate_rejected')
            return self.state
        if self.state is State.LIFT_VERIFY and not (lift and lift.holding()):
            self.abort('grasp_not_confirmed')
            return self.state
        index = SEQUENCE.index(self.state)
        if index + 1 == len(SEQUENCE):
            self.state = State.IDLE
            # ARM-5 applies to failures only; a clean finish returns the permit.
            self.base_motion_allowed = True
        else:
            self.state = SEQUENCE[index + 1]
        return self.state

    def retry(self) -> None:
        """ARM-5: there is no automatic retry. Only a new task clears an abort."""
        raise RuntimeError('aborted grasp tasks are never retried automatically; '
                           'hr_task_manager must create a new task')
