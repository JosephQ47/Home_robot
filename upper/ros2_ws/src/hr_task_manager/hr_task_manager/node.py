"""Single business task arbiter. This node never publishes velocity."""
import threading
import time

from geometry_msgs.msg import PoseStamped
from hr_interfaces.action import ExecuteTask
from hr_interfaces.msg import (FollowPolicy, MotionPhase, PerceptionControl,
                               RobotStatus, TaskStatus, TrackerPolicy)
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .state_machine import TaskState, precheck_reason


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
        self.create_subscription(RobotStatus, '/robot_status', self.on_robot_status, 10)
        self.create_subscription(Odometry, '/odometry/filtered', self.on_odom, 10)
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.server = ActionServer(self, ExecuteTask, '/task/execute', execute_callback=self.execute,
                                   goal_callback=self.goal_callback, cancel_callback=self.cancel_callback)

    def goal_callback(self, request):
        if not request.task_id:
            return GoalResponse.REJECT
        with self.task_lock:
            if self.active is not None or self.reserved_task_id is not None:
                return GoalResponse.REJECT
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
        motion = MotionPhase()
        motion.header.stamp, motion.task_id = stamp, goal.task_id
        motion.phase = MotionPhase.NAVIGATING if enabled else MotionPhase.ZERO
        motion.reason, motion.zero_required = phase, not enabled
        self.phase_pub.publish(motion)

    def finish(self, handle, goal, state, success, outcome, terminal_method):
        terminal_method()
        result = ExecuteTask.Result()
        result.success, result.outcome, result.message = success, outcome, state.message
        self.publish_state(goal, state)
        return result

    def execute(self, handle):
        goal = handle.request
        state = TaskState(goal.task_id)
        with self.task_lock:
            self.active = state
            self.reserved_task_id = None
        self.publish_state(goal, state)
        started = time.monotonic()
        try:
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
                state.transition('FAILED', 'ZERO',
                                 f'navigation action server not available in {nav_timeout:.1f}s',
                                 code='NAV_SERVER_UNAVAILABLE')
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
