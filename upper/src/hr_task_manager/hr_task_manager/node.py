"""Single business task arbiter. This node never publishes velocity."""
import math
import threading
import time

from geometry_msgs.msg import PoseStamped
from hr_interfaces.action import ExecuteArm, ExecuteTask
from hr_interfaces.msg import (FollowPolicy, MotionPhase, PerceptionControl,
                               RobotStatus, TaskStatus, TrackerPolicy)
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .state_machine import (TaskState, admission_reason, arm_precheck_reason,
                            is_arm_task, precheck_reason)


class TaskManager(Node):
    def __init__(self):
        super().__init__('hr_task_manager')
        self.declare_parameter('dependency_timeout_sec', 1.0)
        self.declare_parameter('task_timeout_sec', 30.0)
        self.declare_parameter('mock_navigation_enabled', False)
        # 导航 action server 的发现等待上限。见 execute() 里的说明：
        # 不等就直接 send_goal_async，会把「Nav2 还没起来」误报成「目标被拒绝」。
        self.declare_parameter('nav_server_timeout_sec', 5.0)
        self.declare_parameter('follow_desired_distance_m', 0.0)
        self.declare_parameter('follow_minimum_safe_distance_m', 0.0)
        self.declare_parameter('arm_server_timeout_sec', 5.0)
        self.declare_parameter('arm_task_timeout_sec', 120.0)
        self.declare_parameter('accepted_object_classes', [''])
        self.declare_parameter('accepted_places', [''])
        # Named work pose a grasp is performed from. Empty means the caller has
        # already parked the robot and only the arm stages should run.
        self.declare_parameter('grasp_work_pose', '')
        self.declare_parameter('work_pose_xyyaw', [0.0, 0.0, 0.0])
        self.declare_parameter('base_settle_timeout_sec', 10.0)
        self.robot_status = None
        self.status_time = 0.0
        self.odom_time = 0.0
        self.active = None
        self.reserved_task_id = None
        self.task_lock = threading.Lock()
        self.nav_goal = None
        self.status_pub = self.create_publisher(TaskStatus, '/task/status', 10)
        self.perception_pub = self.create_publisher(PerceptionControl, '/task/perception_control', 10)
        self.tracker_pub = self.create_publisher(TrackerPolicy, '/task/tracker_policy', 10)
        self.follow_pub = self.create_publisher(FollowPolicy, '/task/follow_policy', 10)
        self.phase_pub = self.create_publisher(MotionPhase, '/task/motion_phase', 10)
        self.phase_seq = 0
        # hr_motion_mux treats the phase as an *authorisation*, and an
        # authorisation that is not renewed expires (MUX-4) — that is what makes
        # a dead task manager stop the robot instead of leaving it driving.
        # So the current phase has to be republished as a heartbeat, not only on
        # transitions. Caught by the runtime check in dev_log: with event-only
        # publishing the mux zeroed the base one second into every navigation.
        self.last_phase = None
        # execute() blocks for as long as the task runs, so it must not share a
        # mutually exclusive group with the subscriptions its own safety checks
        # read. A MultiThreadedExecutor alone does not achieve that: without an
        # explicit reentrant group every callback still lands in the node's
        # default mutually exclusive one, the extra threads never get used, and
        # /robot_status goes stale under a long task until the task aborts
        # itself with SAFETY_INVALID. 见 CLAUDE.md「不许在回调里阻塞」。
        group = ReentrantCallbackGroup()
        self.create_timer(0.2, self.republish_phase, callback_group=group)
        self.create_subscription(RobotStatus, '/robot_status', self.on_robot_status, 10,
                                 callback_group=group)
        self.create_subscription(Odometry, '/odometry/filtered', self.on_odom, 10,
                                 callback_group=group)
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose',
                                callback_group=group)
        self.arm = ActionClient(self, ExecuteArm, '/arm/execute', callback_group=group)
        self.arm_goal = None
        self.server = ActionServer(self, ExecuteTask, '/task/execute',
                                   execute_callback=self.execute,
                                   goal_callback=self.goal_callback,
                                   cancel_callback=self.cancel_callback,
                                   callback_group=group)

    def goal_callback(self, request):
        if not request.task_id:
            return GoalResponse.REJECT
        with self.task_lock:
            busy = self.active is not None or self.reserved_task_id is not None
            # Read both facts under the one lock. task_lock is a plain Lock, so a
            # helper that re-acquires it here would deadlock the action server.
            recharging = self.active is not None and self.active.source == 'SYSTEM_BATTERY'
            reason = admission_reason(request.source, request.task_type, busy, recharging)
            if reason:
                self.get_logger().info(
                    f'refusing task {request.task_id} from {request.source}: {reason}')
                return GoalResponse.REJECT
            # ARM_STOP is admissible while busy, but it still must not take the
            # "active" slot — that belongs to whatever it is stopping.
            if not busy:
                self.reserved_task_id = request.task_id
        return GoalResponse.ACCEPT

    def cancel_callback(self, _goal):
        return CancelResponse.ACCEPT

    def on_robot_status(self, msg):
        self.robot_status = msg
        self.status_time = time.monotonic()

    def on_odom(self, _msg):
        self.odom_time = time.monotonic()

    def fresh(self, timestamp):
        return timestamp > 0 and time.monotonic() - timestamp <= float(self.get_parameter('dependency_timeout_sec').value)

    def publish_state(self, goal, state):
        msg = TaskStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.task_id, msg.source, msg.task_type = state.task_id, goal.source, goal.task_type
        msg.stage, msg.status, msg.progress = state.stage, state.status, state.progress
        msg.message, msg.result_code = state.message, state.result_code
        msg.interruption_reason = state.interruption_reason
        self.status_pub.publish(msg)
        return msg

    def publish_controls(self, goal, enabled, phase):
        stamp = self.get_clock().now().to_msg()
        perception = PerceptionControl()
        perception.header.stamp, perception.enabled = stamp, enabled
        perception.task_id, perception.target_class, perception.phase = goal.task_id, goal.target_class, phase
        self.perception_pub.publish(perception)
        tracker = TrackerPolicy()
        tracker.header.stamp, tracker.enabled = stamp, enabled
        tracker.task_id, tracker.target_class, tracker.area_id = goal.task_id, goal.target_class, goal.area_id
        self.tracker_pub.publish(tracker)
        follow = FollowPolicy()
        follow.header.stamp, follow.task_id = stamp, goal.task_id
        follow.enabled = enabled and goal.mode == 'follow'
        follow.desired_distance_m = float(self.get_parameter('follow_desired_distance_m').value)
        follow.minimum_safe_distance_m = float(
            self.get_parameter('follow_minimum_safe_distance_m').value)
        self.follow_pub.publish(follow)
        self.last_phase = (self.phase_for(goal, enabled), goal.task_id, phase, not enabled)
        self.publish_phase(*self.last_phase)

    def publish_phase(self, phase_value, task_id, reason, zero_required):
        motion = MotionPhase()
        motion.header.stamp = self.get_clock().now().to_msg()
        motion.task_id, motion.reason = task_id, reason
        motion.phase, motion.zero_required = phase_value, zero_required
        # hr_motion_mux drops any phase message whose source_seq does not advance,
        # so this counter must increment on every publish, including repeats.
        self.phase_seq += 1
        motion.source_seq = self.phase_seq
        self.phase_pub.publish(motion)

    def republish_phase(self):
        """Renew the current authorisation so hr_motion_mux keeps honouring it.

        zero_required is cleared on repeats: the mandatory zero window belongs to
        the transition itself, and re-asserting it every 200 ms would hold the
        base at zero forever.
        """
        if self.last_phase is None:
            return
        phase_value, task_id, reason, _ = self.last_phase
        self.publish_phase(phase_value, task_id, reason, False)

    @staticmethod
    def phase_for(goal, enabled):
        """Which automatic velocity source this task is allowed to use.

        DOCKING authorises OpenNav Docking's /cmd_vel_dock; everything else that
        may move authorises Nav2's /cmd_vel_nav.
        """
        if not enabled:
            return MotionPhase.ZERO
        if goal.task_type == 'dock':
            return MotionPhase.DOCKING
        if goal.mode == 'follow':
            return MotionPhase.FOLLOWING
        return MotionPhase.NAVIGATING

    def finish(self, handle, goal, state, success, outcome, terminal_method):
        terminal_method()
        result = ExecuteTask.Result()
        result.success, result.outcome, result.message = success, outcome, state.message
        self.publish_state(goal, state)
        return result

    def base_stopped(self):
        """Whether the chassis is settled enough for the arm to move.

        Only what this node can see: the STM32 reports no automatic control and
        nobody has taken over. hr_arm_controller checks the stricter four-way
        interlock itself (ARM-1); this is the cheaper gate that keeps an
        obviously-moving robot from even being asked.
        """
        status = self.robot_status
        if status is None or not self.fresh(self.status_time):
            return False
        return not status.remote_override and status.control_source in (
            RobotStatus.CONTROL_UNKNOWN, RobotStatus.CONTROL_AUTO)

    def navigate_to_work_pose(self, handle, goal, state):
        """Drive to the configured work pose, then hand the base back to ZERO.

        Returns False when the approach did not finish, with `state` already
        carrying the reason. The phase is NAVIGATING only for this stretch: the
        moment it ends the base loses its authorisation again, so there is no
        window in which both the wheels and the arm are allowed to move.
        """
        pose = [float(v) for v in self.get_parameter('work_pose_xyyaw').value]
        if len(pose) != 3:
            state.transition('REJECTED', 'PRECHECK', 'work_pose_xyyaw must be [x, y, yaw]',
                             code='WORK_POSE_UNCONFIGURED')
            return False
        state.transition('RUNNING', 'NAVIGATING', 'driving to the work pose', 0.15)
        self.publish_controls(goal, True, 'NAVIGATING')
        # The web console shows whatever /task/status carries, so a stage that is
        # never published is a stage the operator cannot see the robot is in.
        feedback = ExecuteTask.Feedback()
        feedback.status = self.publish_state(goal, state)
        handle.publish_feedback(feedback)
        nav_timeout = float(self.get_parameter('nav_server_timeout_sec').value)
        if not self.nav.wait_for_server(timeout_sec=nav_timeout):
            state.transition('FAILED', 'ZERO',
                             f'navigation action server not available in {nav_timeout:.1f}s',
                             code='NAV_GOAL_REJECTED')
            return False
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = PoseStamped()
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.header.frame_id = 'map'
        nav_goal.pose.pose.position.x, nav_goal.pose.pose.position.y = pose[0], pose[1]
        nav_goal.pose.pose.orientation.z = math.sin(pose[2] / 2.0)
        nav_goal.pose.pose.orientation.w = math.cos(pose[2] / 2.0)
        send_future = self.nav.send_goal_async(nav_goal)
        while not send_future.done():
            time.sleep(0.02)
        self.nav_goal = send_future.result()
        if self.nav_goal is None or not self.nav_goal.accepted:
            state.transition('FAILED', 'ZERO', 'work pose goal rejected',
                             code='NAV_GOAL_REJECTED')
            return False
        nav_result = self.nav_goal.get_result_async()
        deadline = time.monotonic() + float(self.get_parameter('task_timeout_sec').value)
        while not nav_result.done():
            if handle.is_cancel_requested:
                self.nav_goal.cancel_goal_async()
                state.transition('CANCELED', 'ZERO', 'task canceled', reason='USER_CANCEL')
                return False
            if self.robot_status and self.robot_status.remote_override:
                self.nav_goal.cancel_goal_async()
                state.transition('INTERRUPTED', 'ZERO', 'remote operator took control',
                                 reason='REMOTE_OVERRIDE')
                return False
            if not self.fresh(self.status_time) or not self.robot_status.safety_permit:
                self.nav_goal.cancel_goal_async()
                state.transition('INTERRUPTED', 'ZERO', 'safety dependency became invalid',
                                 reason='SAFETY_INVALID')
                return False
            if time.monotonic() > deadline:
                self.nav_goal.cancel_goal_async()
                state.transition('TIMED_OUT', 'ZERO', 'work pose approach timed out',
                                 reason='TASK_TIMEOUT')
                return False
            time.sleep(0.05)
        self.nav_goal = None
        return True

    def execute_arm(self, handle, goal, state, started, is_stop):
        """Run an arm task. The base stays pinned at ZERO for its whole duration."""
        timeout = float(self.get_parameter('arm_task_timeout_sec').value)
        if is_stop:
            # A stop cancels whatever is running and asks the arm to halt. It
            # never waits for a slot and never reports failure for being late.
            if self.nav_goal is not None:
                self.nav_goal.cancel_goal_async()
            if self.arm_goal is not None:
                self.arm_goal.cancel_goal_async()
            self.send_arm(goal, 'ARM_STOP', wait=False)
            state.transition('COMPLETED', 'DONE', 'arm stop requested', 1.0)
            return self.finish(handle, goal, state, True, 'COMPLETED', handle.succeed)

        reason = arm_precheck_reason(self.fresh(self.status_time), self.robot_status,
                                     self.arm.server_is_ready(), self.base_stopped())
        if reason:
            state.transition('REJECTED', 'PRECHECK', 'arm task precheck rejected', code=reason)
            return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)
        if goal.task_type == 'ARM_GRASP' and not self.class_accepted(goal.target_class):
            state.transition('REJECTED', 'PRECHECK',
                             f'object class "{goal.target_class}" is not accepted',
                             code='OBJECT_CLASS_UNSUPPORTED')
            return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)
        if goal.task_type == 'ARM_RELEASE' and not self.place_accepted(goal.area_id):
            state.transition('REJECTED', 'PRECHECK',
                             f'place "{goal.area_id}" is not accepted',
                             code='PLACE_UNSUPPORTED')
            return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)

        # NAVIGATE_TO_WORKPOSE. The arm state machine has this stage but does not
        # drive the base; that is this node's job (技术方案 §3.12.5).
        if goal.task_type == 'ARM_GRASP' and str(self.get_parameter('grasp_work_pose').value):
            if not self.navigate_to_work_pose(handle, goal, state):
                return self.finish(handle, goal, state, False, state.status, handle.abort)

        # The arm may only move while the base is authorised to do nothing.
        # Publishing ZERO here is what makes hr_motion_mux refuse every automatic
        # velocity source for the duration, so "the base must not move" is
        # enforced by the speed chain rather than by everyone remembering.
        state.transition('RUNNING', 'ZERO', 'arm task active', 0.35)
        self.publish_controls(goal, False, 'ZERO')

        # BASE_STOP_CONFIRM. Wait for the chassis to actually settle before the
        # arm is even asked; hr_arm_controller re-checks this with its own
        # four-way interlock, and a task that fails there wastes a whole approach.
        settle_deadline = time.monotonic() + float(
            self.get_parameter('base_settle_timeout_sec').value)
        while not self.base_stopped():
            if time.monotonic() > settle_deadline:
                state.transition('FAILED', 'ZERO', 'chassis did not settle',
                                 code='BASE_NOT_STOPPED')
                return self.finish(handle, goal, state, False, 'FAILED', handle.abort)
            if handle.is_cancel_requested:
                state.transition('CANCELED', 'ZERO', 'task canceled', reason='USER_CANCEL')
                return self.finish(handle, goal, state, False, 'CANCELED', handle.canceled)
            time.sleep(0.05)
        feedback = ExecuteTask.Feedback()
        feedback.status = self.publish_state(goal, state)
        handle.publish_feedback(feedback)

        arm_timeout = float(self.get_parameter('arm_server_timeout_sec').value)
        if not self.arm.wait_for_server(timeout_sec=arm_timeout):
            state.transition('FAILED', 'ZERO',
                             f'arm action server not available in {arm_timeout:.1f}s',
                             code='ARM_UNAVAILABLE')
            return self.finish(handle, goal, state, False, 'FAILED', handle.abort)
        self.arm_goal = self.send_arm(goal, goal.task_type, wait=True)
        if self.arm_goal is None or not self.arm_goal.accepted:
            state.transition('FAILED', 'ZERO', 'arm goal rejected', code='ARM_GOAL_REJECTED')
            return self.finish(handle, goal, state, False, 'FAILED', handle.abort)

        result_future = self.arm_goal.get_result_async()
        while not result_future.done():
            if handle.is_cancel_requested:
                self.arm_goal.cancel_goal_async()
                state.transition('CANCELED', 'ZERO', 'task canceled', reason='USER_CANCEL')
                return self.finish(handle, goal, state, False, 'CANCELED', handle.canceled)
            if self.robot_status and self.robot_status.remote_override:
                self.arm_goal.cancel_goal_async()
                state.transition('INTERRUPTED', 'ZERO', 'remote operator took control',
                                 reason='REMOTE_OVERRIDE')
                return self.finish(handle, goal, state, False, 'INTERRUPTED', handle.abort)
            if not self.fresh(self.status_time) or not self.robot_status.safety_permit:
                self.arm_goal.cancel_goal_async()
                state.transition('INTERRUPTED', 'ZERO', 'safety dependency became invalid',
                                 reason='SAFETY_INVALID')
                return self.finish(handle, goal, state, False, 'INTERRUPTED', handle.abort)
            if time.monotonic() - started > timeout:
                self.arm_goal.cancel_goal_async()
                state.transition('TIMED_OUT', 'ZERO', 'arm task timed out', reason='TASK_TIMEOUT')
                return self.finish(handle, goal, state, False, 'TIMED_OUT', handle.abort)
            time.sleep(0.05)

        outcome = result_future.result().result
        if not outcome.success:
            # Carry the arm's own failed stage through, so "it failed" is always
            # accompanied by "at which step".
            state.transition('FAILED', outcome.failed_stage or 'ZERO',
                             outcome.message or 'arm task failed', code='ARM_TASK_FAILED')
            return self.finish(handle, goal, state, False, 'FAILED', handle.abort)
        state.transition('COMPLETED', 'DONE', outcome.message or 'arm task completed', 1.0)
        return self.finish(handle, goal, state, True, 'COMPLETED', handle.succeed)

    def send_arm(self, goal, command, wait):
        arm_goal = ExecuteArm.Goal()
        arm_goal.task_id, arm_goal.command = goal.task_id, command
        arm_goal.object_class, arm_goal.place_id = goal.target_class, goal.area_id
        future = self.arm.send_goal_async(arm_goal)
        if not wait:
            return None
        while not future.done():
            time.sleep(0.02)
        return future.result()

    def class_accepted(self, object_class):
        allowed = [c for c in self.get_parameter('accepted_object_classes').value if c]
        return bool(object_class) and (not allowed or object_class in allowed)

    def place_accepted(self, place):
        allowed = [p for p in self.get_parameter('accepted_places').value if p]
        return bool(place) and (not allowed or place in allowed)

    def execute(self, handle):
        goal = handle.request
        state = TaskState(goal.task_id, goal.source)
        is_stop = goal.task_type == 'ARM_STOP'
        with self.task_lock:
            # ARM_STOP runs alongside whatever it is stopping; it must not evict
            # that task from the active slot or the stopped task loses its state.
            if not is_stop:
                self.active = state
                self.reserved_task_id = None
        self.publish_state(goal, state)
        started = time.monotonic()
        try:
            if is_arm_task(goal.task_type):
                return self.execute_arm(handle, goal, state, started, is_stop)
            reason = precheck_reason(self.fresh(self.status_time), self.fresh(self.odom_time),
                                     self.robot_status, self.nav.server_is_ready())
            if reason:
                state.transition('REJECTED', 'PRECHECK', 'task precheck rejected', code=reason)
                return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)
            if not bool(self.get_parameter('mock_navigation_enabled').value):
                state.transition('REJECTED', 'PRECHECK',
                                 'map goal resolver is not configured', code='GOAL_RESOLVER_UNAVAILABLE')
                return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)
            if goal.mode == 'follow':
                desired = float(self.get_parameter('follow_desired_distance_m').value)
                minimum = float(self.get_parameter('follow_minimum_safe_distance_m').value)
                if desired <= 0.0 or minimum <= 0.0 or desired <= minimum:
                    state.transition('REJECTED', 'PRECHECK',
                                     'follow distances are not configured',
                                     code='FOLLOW_POLICY_UNCONFIGURED')
                    return self.finish(handle, goal, state, False, 'REJECTED', handle.abort)
            state.transition('RUNNING', 'NAVIGATING', 'navigation goal active', 0.1)
            self.publish_controls(goal, True, 'NAVIGATING')
            feedback = ExecuteTask.Feedback(); feedback.status = self.publish_state(goal, state)
            handle.publish_feedback(feedback)
            # 必须先等 action server 被发现再发目标。
            # 不等的话，启动后立刻下发的第一个任务会拿到 accepted=False，
            # 被判成 NAV_GOAL_REJECTED —— 但真实原因是 Nav2 还没起来，
            # 两者的处置完全不同（前者该换目标点，后者该等或查 Nav2）。
            # 这个竞态在 verify_task_lifecycle.py 上表现为偶发失败
            # 「normal task did not complete」，真机上表现为开机后第一个任务
            # 无缘无故失败、重试一次又好了。
            nav_timeout = float(self.get_parameter('nav_server_timeout_sec').value)
            if not self.nav.wait_for_server(timeout_sec=nav_timeout):
                # 复用既有 NAV_GOAL_REJECTED：技术方案称错误码需评审后冻结，
                # 不擅自新增。代价是「Nav2 没起来」和「目标被拒绝」在错误码上
                # 无法区分，故把原因写进 message，排障时看这句。
                state.transition('FAILED', 'ZERO',
                                 f'navigation action server not available in {nav_timeout:.1f}s',
                                 code='NAV_GOAL_REJECTED')
                return self.finish(handle, goal, state, False, 'FAILED', handle.abort)
            nav_goal = NavigateToPose.Goal()
            nav_goal.pose = PoseStamped()
            nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
            nav_goal.pose.header.frame_id = 'map'
            nav_goal.pose.pose.orientation.w = 1.0  # Mock adapter target only; real goals come from accepted map config.
            send_future = self.nav.send_goal_async(nav_goal)
            while not send_future.done():
                time.sleep(0.02)
            self.nav_goal = send_future.result()
            if self.nav_goal is None or not self.nav_goal.accepted:
                state.transition('FAILED', 'ZERO', 'navigation goal rejected', code='NAV_GOAL_REJECTED')
                return self.finish(handle, goal, state, False, 'FAILED', handle.abort)
            nav_result = self.nav_goal.get_result_async()
            while not nav_result.done():
                if handle.is_cancel_requested:
                    self.nav_goal.cancel_goal_async()
                    state.transition('CANCELED', 'ZERO', 'task canceled', reason='USER_CANCEL')
                    return self.finish(handle, goal, state, False, 'CANCELED', handle.canceled)
                if self.robot_status and self.robot_status.remote_override:
                    self.nav_goal.cancel_goal_async()
                    state.transition('INTERRUPTED', 'ZERO', 'remote operator took control', reason='REMOTE_OVERRIDE')
                    return self.finish(handle, goal, state, False, 'INTERRUPTED', handle.abort)
                if not self.fresh(self.status_time) or not self.robot_status.safety_permit:
                    self.nav_goal.cancel_goal_async()
                    state.transition('INTERRUPTED', 'ZERO', 'safety dependency became invalid', reason='SAFETY_INVALID')
                    return self.finish(handle, goal, state, False, 'INTERRUPTED', handle.abort)
                if time.monotonic() - started > float(self.get_parameter('task_timeout_sec').value):
                    self.nav_goal.cancel_goal_async()
                    state.transition('TIMED_OUT', 'ZERO', 'task timed out', reason='TASK_TIMEOUT')
                    return self.finish(handle, goal, state, False, 'TIMED_OUT', handle.abort)
                time.sleep(0.05)
            state.transition('COMPLETED', 'DONE', 'task completed by mock navigation', 1.0)
            return self.finish(handle, goal, state, True, 'COMPLETED', handle.succeed)
        finally:
            self.publish_controls(goal, False, state.status)
            self.publish_state(goal, state)
            self.arm_goal = None
            if not is_stop:
                self.nav_goal = None
                with self.task_lock:
                    self.active = None
                    self.reserved_task_id = None


def main(args=None):
    rclpy.init(args=args)
    node = TaskManager()
    executor = MultiThreadedExecutor(num_threads=4); executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
