"""Fail-closed controller for short odom goals and already-validated follow targets."""
import math
import time

from geometry_msgs.msg import PoseStamped, Twist
from hr_interfaces.msg import FollowPolicy, FollowTarget, RobotStatus
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node

from .control import follow_command, goal_command


class LocalMotion(Node):
    def __init__(self):
        super().__init__('hr_local_motion')
        self.declare_parameter('output_enabled', False)
        self.declare_parameter('max_goal_distance_m', 0.5)
        self.declare_parameter('max_goal_duration_sec', 5.0)
        self.declare_parameter('max_linear_mps', 0.10)
        self.declare_parameter('max_angular_rps', 0.30)
        self.declare_parameter('input_timeout_sec', 0.5)
        self.declare_parameter('required_downstream_node', 'collision_monitor')
        if not bool(self.get_parameter('output_enabled').value):
            raise RuntimeError('local motion refuses to start unless output_enabled=true')
        self.odom = None; self.odom_time = 0.0
        self.robot = None; self.robot_time = 0.0
        self.goal = None; self.goal_started = 0.0
        self.target = None; self.target_time = 0.0
        self.follow = None
        self.pub = self.create_publisher(Twist, '/cmd_vel_auto', 10)
        self.create_subscription(Odometry, '/odometry/filtered', self.on_odom, 10)
        self.create_subscription(RobotStatus, '/robot_status', self.on_robot, 10)
        self.create_subscription(PoseStamped, '/goal_pose', self.on_goal, 10)
        self.create_subscription(FollowTarget, '/follow_target', self.on_target, 10)
        self.create_subscription(FollowPolicy, '/task/follow_policy', self.on_follow, 10)
        self.create_timer(0.05, self.tick)

    def on_odom(self, msg): self.odom, self.odom_time = msg, time.monotonic()
    def on_robot(self, msg): self.robot, self.robot_time = msg, time.monotonic()
    def on_target(self, msg): self.target, self.target_time = msg, time.monotonic()
    def on_follow(self, msg): self.follow = msg

    def on_goal(self, msg):
        if msg.header.frame_id != 'odom' or self.odom is None:
            self.get_logger().error('rejected RViz goal: frame must be odom and odometry must be ready')
            return
        p = self.odom.pose.pose.position
        distance = math.hypot(msg.pose.position.x - p.x, msg.pose.position.y - p.y)
        if distance > float(self.get_parameter('max_goal_distance_m').value):
            self.get_logger().error(f'rejected RViz goal: {distance:.2f} m exceeds bounded limit')
            return
        self.goal, self.goal_started = msg, time.monotonic()

    def fresh(self, stamp):
        return stamp > 0 and time.monotonic() - stamp <= float(self.get_parameter('input_timeout_sec').value)

    def safe(self):
        return (self.fresh(self.odom_time) and self.fresh(self.robot_time) and self.robot and
                self.robot.stm32_link_ok and self.robot.command_fresh and self.robot.wheel_odom_valid and
                self.robot.safety_permit and not self.robot.remote_override and self.robot.watchdog_healthy)

    def downstream_ready(self):
        required = str(self.get_parameter('required_downstream_node').value)
        if required == '*':
            return self.pub.get_subscription_count() > 0
        return any(info.node_name == required
                   for info in self.get_subscriptions_info_by_topic('/cmd_vel_auto'))

    def publish(self, linear=0.0, angular=0.0):
        msg = Twist(); msg.linear.x = float(linear); msg.angular.z = float(angular); self.pub.publish(msg)

    def tick(self):
        if not self.safe() or not self.downstream_ready():
            self.goal = None; self.publish(); return
        max_linear = float(self.get_parameter('max_linear_mps').value)
        max_angular = float(self.get_parameter('max_angular_rps').value)
        if self.follow and self.follow.enabled:
            if not self.fresh(self.target_time) or not self.target or not self.target.follow_allowed:
                self.publish(); return
            linear, angular = follow_command(self.target.range_m, self.target.bearing_rad,
                                             self.follow.desired_distance_m,
                                             self.follow.minimum_safe_distance_m,
                                             max_linear, max_angular)
            self.publish(linear, angular); return
        if self.goal:
            if time.monotonic() - self.goal_started > float(self.get_parameter('max_goal_duration_sec').value):
                self.goal = None; self.publish(); return
            p = self.odom.pose.pose.position; q = self.odom.pose.pose.orientation
            yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1-2*(q.y*q.y + q.z*q.z))
            linear, angular, done = goal_command(p.x, p.y, yaw, self.goal.pose.position.x,
                                                  self.goal.pose.position.y, max_linear, max_angular)
            if done: self.goal = None
            self.publish(linear, angular); return
        self.publish()

    def destroy_node(self):
        if rclpy.ok(context=self.context):
            self.publish()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = LocalMotion()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
