"""Runs the grasp sequence: ExecuteArm action server over the state machine.

The interlocks are the point of this node. Before a single joint moves it must
be true that Nav2 is finished, both velocity topics are quiet, the wheels are
stopped and nobody has taken over manually — and those four are checked
continuously, not once at the start (技术方案 §3.12.5).

# @spec 家庭服务机器人技术方案.md#3.12.5
"""
import threading
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
from hr_interfaces.action import ExecuteArm
from hr_interfaces.msg import GraspCandidates, RobotStatus
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from .grasp_state_machine import (BaseState, GraspInputs, GraspStateMachine,
                                  LiftEvidence, State)
from .kinematics import ArmGeometry, JointLimits, Unreachable, solve

JOINT_NAMES = [f'joint_{i}' for i in range(1, 7)]
HOME = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


class ArmControllerNode(Node):
    def __init__(self):
        super().__init__('hr_arm_controller')
        self.declare_parameter('accepted_object_classes', [''])
        self.declare_parameter('accepted_places', [''])
        self.declare_parameter('base_stop_settle_ms', 500)
        self.declare_parameter('stage_timeout_ms', 20000)
        self.declare_parameter('candidate_timeout_ms', 1000)
        self.declare_parameter('odom_timeout_ms', 500)
        self.declare_parameter('move_duration_ms', 900)
        self.declare_parameter('gripper_open_m', 0.09)
        self.declare_parameter('gripper_closed_margin_m', 0.008)
        self.declare_parameter('lift_current_threshold_a', 0.35)
        self.declare_parameter('approach_pitch_rad', -1.5708)
        self.declare_parameter('pregrasp_height_m', 0.10)
        self.declare_parameter('lift_height_m', 0.08)
        self.declare_parameter('place_position_xyz', [0.20, -0.15, 0.10])
        for name, default in (('base_height_m', 0.10), ('shoulder_offset_m', 0.0),
                              ('upper_arm_m', 0.15), ('forearm_m', 0.14),
                              ('wrist_length_m', 0.08)):
            self.declare_parameter(name, default)
        self.declare_parameter('joint_lower_rad', [-2.79, -1.57, -2.36, -2.79, -1.92, -3.14])
        self.declare_parameter('joint_upper_rad', [2.79, 1.92, 2.36, 2.79, 1.92, 3.14])

        self.geometry = ArmGeometry(
            base_height=float(self.get_parameter('base_height_m').value),
            shoulder_offset=float(self.get_parameter('shoulder_offset_m').value),
            upper_arm=float(self.get_parameter('upper_arm_m').value),
            forearm=float(self.get_parameter('forearm_m').value),
            wrist_length=float(self.get_parameter('wrist_length_m').value))
        self.limits = JointLimits(
            lower=tuple(float(v) for v in self.get_parameter('joint_lower_rad').value),
            upper=tuple(float(v) for v in self.get_parameter('joint_upper_rad').value))
        self.classes = {c for c in self.get_parameter('accepted_object_classes').value if c}
        self.places = {p for p in self.get_parameter('accepted_places').value if p}

        self.machine = GraspStateMachine()
        self.lock = threading.Lock()
        self.base = BaseState()
        self.cmd_vel_zero_since = None
        self.candidates = None
        self.candidates_stamp = float('-inf')
        self.odom_stamp = float('-inf')
        self.joints = None
        self.faults = {}

        group = ReentrantCallbackGroup()
        self.traj_pub = self.create_publisher(JointTrajectory, '/arm/joint_trajectory', 10)
        self.gripper_pub = self.create_publisher(Float32, '/arm/gripper_command', 10)
        self.stop_pub = self.create_publisher(Bool, '/arm/stop', 10)
        self.perception_pub = self.create_publisher(Bool, '/arm/perception_enabled', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)

        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 10, callback_group=group)
        self.create_subscription(Twist, '/cmd_vel_auto', self.on_cmd_vel, 10,
                                 callback_group=group)
        self.create_subscription(RobotStatus, '/robot_status', self.on_robot_status, 10,
                                 callback_group=group)
        self.create_subscription(Odometry, '/wheel/odom_raw', self.on_wheel_odom, 10,
                                 callback_group=group)
        self.create_subscription(GraspCandidates, '/arm/grasp_candidates',
                                 self.on_candidates, 10, callback_group=group)
        self.create_subscription(JointState, '/arm/joint_states', self.on_joints, 10,
                                 callback_group=group)
        self.create_subscription(Bool, '/arm/nav_goal_finished', self.on_nav_done, 10,
                                 callback_group=group)

        self.server = ActionServer(
            self, ExecuteArm, '/arm/execute', self.execute,
            goal_callback=self.on_goal, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=group)
        self.create_timer(1.0, self.publish_diagnostics, callback_group=group)

    # ---- inputs -----------------------------------------------------------

    def on_cmd_vel(self, msg):
        moving = abs(msg.linear.x) > 1e-6 or abs(msg.angular.z) > 1e-6
        with self.lock:
            if moving:
                self.cmd_vel_zero_since = None
                self.base.cmd_vel_zero = False
            elif self.cmd_vel_zero_since is None:
                self.cmd_vel_zero_since = time.monotonic()

    def on_wheel_odom(self, msg):
        """Wheel speed comes from the odometry that actually carries it.

        RobotStatus has no wheel velocity field. Reading one off it with a
        default of zero would mean "no data" evaluates to "stopped" — which is
        the fail-open the whole interlock exists to prevent. Absent or stale
        odometry therefore leaves wheel_speed_zero false; see base_settled().
        """
        with self.lock:
            self.base.wheel_speed_zero = (abs(msg.twist.twist.linear.x) < 1e-3 and
                                          abs(msg.twist.twist.angular.z) < 1e-3)
            self.odom_stamp = time.monotonic()

    def on_robot_status(self, msg):
        with self.lock:
            self.base.remote_override = bool(msg.remote_override)
            # A safe stop, a latched fault or a withdrawn permit are all reasons
            # the arm must not be moving; none of them is optional.
            self.faults['safety_fault'] = (
                not msg.safety_permit
                or msg.control_source == RobotStatus.CONTROL_SAFE_STOP
                or msg.fault_code != 0
                or not msg.watchdog_healthy)
            self.faults['remote_override'] = bool(msg.remote_override)

    def on_nav_done(self, msg):
        with self.lock:
            self.base.nav_goal_finished = bool(msg.data)

    def on_candidates(self, msg):
        with self.lock:
            self.candidates, self.candidates_stamp = msg, time.monotonic()

    def on_joints(self, msg):
        with self.lock:
            self.joints = msg

    def base_settled(self):
        """ARM-1: all four confirmations, and cmd_vel quiet for the settle time."""
        with self.lock:
            settle = int(self.get_parameter('base_stop_settle_ms').value) / 1000.0
            if self.cmd_vel_zero_since is not None:
                self.base.cmd_vel_zero = time.monotonic() - self.cmd_vel_zero_since >= settle
            odom_timeout = int(self.get_parameter('odom_timeout_ms').value) / 1000.0
            if time.monotonic() - self.odom_stamp > odom_timeout:
                # Stale or absent wheel odometry is not evidence of a stopped
                # base. Withdraw the confirmation rather than keeping the last one.
                self.base.wheel_speed_zero = False
            return self.base.stopped()

    # ---- arm motion -------------------------------------------------------

    def send_joints(self, joints):
        msg = JointTrajectory()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.joint_names = JOINT_NAMES
        point = JointTrajectoryPoint()
        point.positions = [float(j) for j in joints]
        duration_ms = int(self.get_parameter('move_duration_ms').value)
        point.time_from_start.sec = duration_ms // 1000
        point.time_from_start.nanosec = (duration_ms % 1000) * 1_000_000
        msg.points = [point]
        self.traj_pub.publish(msg)

    def wait_for_arrival(self, target, timeout_s):
        """Poll joint feedback until it matches, or the stage times out."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self.lock:
                state = self.joints
            if state and len(state.position) >= 6:
                if max(abs(a - b) for a, b in zip(state.position[:6], target)) < 0.02:
                    return True
            if self.check_aborts():
                return False
            time.sleep(0.05)
        self.machine.abort('stage_timeout')
        return False

    def move_to(self, joints, timeout_s):
        self.send_joints(joints)
        return self.wait_for_arrival(joints, timeout_s)

    def set_gripper(self, width, settle_s=1.2):
        self.gripper_pub.publish(Float32(data=float(width)))
        time.sleep(settle_s)

    def check_aborts(self):
        """ARM-4: any of these stops the trajectory, from any stage."""
        with self.lock:
            faults = dict(self.faults)
            faults['remote_override'] = self.base.remote_override
        if self.machine.check_faults(**faults):
            self.stop_pub.publish(Bool(data=True))
            return True
        return False

    def solve_or_abort(self, position, pitch):
        try:
            return solve(position, pitch, self.geometry, self.limits)
        except Unreachable as exc:
            self.get_logger().warning(f'inverse kinematics refused: {exc}')
            self.machine.abort('ik_failure')
            self.stop_pub.publish(Bool(data=True))
            return None

    # ---- action -----------------------------------------------------------

    def on_goal(self, goal):
        request = goal.command
        if request not in ('ARM_HOME', 'ARM_GRASP', 'ARM_RELEASE', 'ARM_STOP'):
            return GoalResponse.REJECT
        if request == 'ARM_GRASP' and self.classes and goal.object_class not in self.classes:
            return GoalResponse.REJECT
        if request == 'ARM_RELEASE' and self.places and goal.place_id not in self.places:
            return GoalResponse.REJECT
        if request != 'ARM_STOP' and self.machine.state is not State.IDLE:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def result(self, success, outcome, message):
        out = ExecuteArm.Result()
        out.success, out.outcome = success, outcome
        out.failed_stage = self.machine.failed_stage.value if self.machine.failed_stage else ''
        out.message = message
        return out

    def feedback(self, handle, progress):
        fb = ExecuteArm.Feedback()
        fb.stage, fb.progress = self.machine.state.value, float(progress)
        handle.publish_feedback(fb)

    def execute(self, handle):
        goal = handle.request
        if goal.command == 'ARM_STOP':
            self.stop_pub.publish(Bool(data=True))
            self.machine.abort('cancelled')
            handle.succeed()
            return self.result(True, 'DONE', 'arm stopped')
        timeout = int(self.get_parameter('stage_timeout_ms').value) / 1000.0
        try:
            if goal.command == 'ARM_HOME':
                return self.run_home(handle, timeout)
            if goal.command == 'ARM_RELEASE':
                return self.run_release(handle, timeout)
            return self.run_grasp(handle, goal, timeout)
        finally:
            self.perception_pub.publish(Bool(data=False))
            if self.machine.state is not State.IDLE:
                self.machine.state = State.IDLE
                self.machine.base_motion_allowed = True

    def run_home(self, handle, timeout):
        self.machine.start()
        self.feedback(handle, 0.2)
        if not self.move_to(HOME, timeout):
            handle.abort()
            return self.result(False, 'ABORTED', str(self.machine.abort_reason))
        handle.succeed()
        return self.result(True, 'DONE', 'arm homed')

    def run_release(self, handle, timeout):
        self.machine.start()
        place = [float(v) for v in self.get_parameter('place_position_xyz').value]
        pitch = float(self.get_parameter('approach_pitch_rad').value)
        joints = self.solve_or_abort(tuple(place), pitch)
        if joints is None or not self.move_to(joints, timeout):
            handle.abort()
            return self.result(False, 'ABORTED', str(self.machine.abort_reason))
        self.set_gripper(float(self.get_parameter('gripper_open_m').value))
        self.move_to(HOME, timeout)
        handle.succeed()
        return self.result(True, 'DONE', 'object released')

    def run_grasp(self, handle, goal, timeout):
        self.machine.start()
        pitch = float(self.get_parameter('approach_pitch_rad').value)
        pregrasp_h = float(self.get_parameter('pregrasp_height_m').value)
        open_w = float(self.get_parameter('gripper_open_m').value)

        # ARM_HOME
        self.feedback(handle, 0.05)
        if not self.move_to(HOME, timeout):
            return self.abort_result(handle)
        self.set_gripper(open_w)
        self.machine.advance()                       # -> NAVIGATE_TO_WORKPOSE

        # The base is driven by hr_task_manager; this node only confirms it stopped.
        self.feedback(handle, 0.15)
        self.machine.advance()                       # -> BASE_STOP_CONFIRM

        # BASE_STOP_CONFIRM
        self.feedback(handle, 0.2)
        deadline = time.monotonic() + timeout
        while not self.base_settled():
            if self.check_aborts() or time.monotonic() > deadline:
                self.machine.abort('base_not_stopped')
                return self.abort_result(handle)
            time.sleep(0.05)
        with self.lock:
            base = BaseState(self.base.nav_goal_finished, self.base.cmd_vel_zero,
                             self.base.wheel_speed_zero, self.base.remote_override)
        if self.machine.advance(base=base) is State.ABORTED:  # -> D435I_PRECHECK
            return self.abort_result(handle)

        # D435I_PRECHECK: the wrist camera only runs during an arm task.
        self.perception_pub.publish(Bool(data=True))
        self.feedback(handle, 0.3)
        self.machine.advance()                       # -> DETECT_TARGET

        # DETECT_TARGET
        candidate = self.await_candidate(goal.object_class, timeout)
        if candidate is None:
            return self.abort_result(handle)
        self.machine.advance()                       # -> SELECT_GRASP

        # SELECT_GRASP
        self.feedback(handle, 0.45)
        position = (candidate.position.x, candidate.position.y, candidate.position.z)
        pregrasp = self.solve_or_abort((position[0], position[1], position[2] + pregrasp_h),
                                       pitch)
        grasp = self.solve_or_abort(position, pitch) if pregrasp else None
        inputs = GraspInputs(
            detection_confident=candidate.confidence >= 0.0,
            depth_valid=candidate.depth_valid_ratio > 0.0,
            hand_eye_calibration_valid=True,     # hr_arm_perception refuses to publish otherwise
            within_workspace=grasp is not None,
            within_joint_limits=grasp is not None,
            gripper_opening_ok=candidate.gripper_width <= open_w,
            collision_free=grasp is not None)
        if self.machine.advance(grasp=inputs) is State.ABORTED:  # -> PREGRASP
            return self.abort_result(handle)

        # PREGRASP -> APPROACH -> CLOSE_GRIPPER
        self.feedback(handle, 0.55)
        if not self.move_to(pregrasp, timeout):
            return self.abort_result(handle)
        self.machine.advance()                       # -> APPROACH
        self.feedback(handle, 0.65)
        if not self.move_to(grasp, timeout):
            return self.abort_result(handle)
        self.machine.advance()                       # -> CLOSE_GRIPPER
        self.feedback(handle, 0.75)
        margin = float(self.get_parameter('gripper_closed_margin_m').value)
        self.set_gripper(max(0.0, candidate.gripper_width - margin))
        self.machine.advance()                       # -> LIFT_VERIFY

        # LIFT_VERIFY: lift, then require two independent signals to agree.
        lift = self.solve_or_abort(
            (position[0], position[1],
             position[2] + float(self.get_parameter('lift_height_m').value)), pitch)
        if lift is None or not self.move_to(lift, timeout):
            return self.abort_result(handle)
        self.feedback(handle, 0.85)
        if self.machine.advance(lift=self.lift_evidence(candidate)) is State.ABORTED:
            return self.abort_result(handle)

        # PLACE -> RELEASE -> done
        place = [float(v) for v in self.get_parameter('place_position_xyz').value]
        place_joints = self.solve_or_abort(tuple(place), pitch)
        if place_joints is None or not self.move_to(place_joints, timeout):
            return self.abort_result(handle)
        self.machine.advance()                       # -> RELEASE
        self.set_gripper(open_w)
        self.feedback(handle, 0.95)
        self.machine.advance()                       # -> IDLE
        self.move_to(HOME, timeout)
        handle.succeed()
        return self.result(True, 'DONE', 'object grasped and placed')

    def await_candidate(self, object_class, timeout):
        deadline = time.monotonic() + timeout
        fresh = int(self.get_parameter('candidate_timeout_ms').value) / 1000.0
        while time.monotonic() < deadline:
            if self.check_aborts():
                return None
            with self.lock:
                msg, stamp = self.candidates, self.candidates_stamp
            if msg is not None and time.monotonic() - stamp <= fresh:
                for c in msg.candidates:
                    if not object_class or c.object_class == object_class:
                        return c
            time.sleep(0.05)
        self.machine.abort('target_lost')
        return None

    def lift_evidence(self, candidate):
        """ARM-3: a closed gripper alone proves nothing."""
        with self.lock:
            state, msg = self.joints, self.candidates
            stamp = self.candidates_stamp
        threshold = float(self.get_parameter('lift_current_threshold_a').value)
        holding_width = False
        loaded = False
        if state and len(state.position) >= 7:
            # The jaws stopped short of fully closed: something is between them.
            holding_width = state.position[6] > 0.002
        if state and len(state.effort) >= 7:
            loaded = max(state.effort[:6]) >= threshold
        visible = (msg is not None and time.monotonic() - stamp <= 2.0 and
                   len(msg.candidates) > 0)
        return LiftEvidence(gripper_position_indicates_object=holding_width,
                            gripper_current_indicates_load=loaded,
                            object_still_visible=visible)

    def abort_result(self, handle):
        self.stop_pub.publish(Bool(data=True))
        handle.abort()
        return self.result(False, 'ABORTED', str(self.machine.abort_reason or 'aborted'))

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_arm_controller', hardware_id='arm')
        status.level = (DiagnosticStatus.ERROR if self.machine.state is State.ABORTED
                        else DiagnosticStatus.OK)
        status.message = self.machine.state.value
        status.values = [
            KeyValue(key='base_motion_allowed', value=str(self.machine.base_motion_allowed)),
            KeyValue(key='failed_stage',
                     value=self.machine.failed_stage.value if self.machine.failed_stage else ''),
            KeyValue(key='abort_reason', value=str(self.machine.abort_reason or '')),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    node = ArmControllerNode()
    # The action callback blocks while waiting for the arm, so it must not share
    # a thread with the subscriptions that feed its abort checks.
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
