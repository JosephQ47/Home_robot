"""Safe ROS-only device and Nav2 mocks. This module never publishes velocity."""
import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped
from hr_interfaces.msg import RobotStatus
from nav2_msgs.action import FollowWaypoints, NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Imu, LaserScan
from tf2_ros import TransformBroadcaster


class MockSystem(Node):
    def __init__(self):
        super().__init__('hr_mock_system')
        self.declare_parameter('safety_permit', True)
        self.declare_parameter('remote_override', False)
        self.declare_parameter('sensor_valid', True)
        self.declare_parameter('publish_scan', True)
        self.declare_parameter('publish_robot_status', True)
        self.declare_parameter('navigation_delay_sec', 1.0)
        self.status_pub = self.create_publisher(RobotStatus, '/robot_status', 10)
        self.odom_pub = self.create_publisher(Odometry, '/wheel/odom_raw', 10)
        self.filtered_pub = self.create_publisher(Odometry, '/odometry/filtered', 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.tf = TransformBroadcaster(self)
        self.create_timer(0.1, self.publish_sensor_state)
        self.create_timer(1.0, self.publish_diagnostics)
        self.nav_server = ActionServer(self, NavigateToPose, '/navigate_to_pose',
            execute_callback=self.execute_nav, goal_callback=self.accept_goal,
            cancel_callback=self.accept_cancel)
        self.waypoint_server = ActionServer(self, FollowWaypoints, '/follow_waypoints',
            execute_callback=self.execute_waypoints, goal_callback=self.accept_goal,
            cancel_callback=self.accept_cancel)

    def accept_goal(self, _request):
        return GoalResponse.ACCEPT

    def accept_cancel(self, _goal):
        return CancelResponse.ACCEPT

    async def execute_nav(self, goal):
        deadline = time.monotonic() + float(self.get_parameter('navigation_delay_sec').value)
        feedback = NavigateToPose.Feedback()
        while time.monotonic() < deadline:
            if goal.is_cancel_requested:
                goal.canceled()
                return NavigateToPose.Result()
            feedback.distance_remaining = max(0.0, deadline - time.monotonic())
            goal.publish_feedback(feedback)
            time.sleep(0.05)
        goal.succeed()
        return NavigateToPose.Result()

    async def execute_waypoints(self, goal):
        deadline = time.monotonic() + float(self.get_parameter('navigation_delay_sec').value)
        while time.monotonic() < deadline:
            if goal.is_cancel_requested:
                goal.canceled()
                return FollowWaypoints.Result()
            time.sleep(0.05)
        goal.succeed()
        return FollowWaypoints.Result()

    def publish_sensor_state(self):
        now = self.get_clock().now().to_msg()
        valid = bool(self.get_parameter('sensor_valid').value)
        remote = bool(self.get_parameter('remote_override').value)
        permit = bool(self.get_parameter('safety_permit').value) and not remote
        status = RobotStatus()
        status.header.stamp = now
        status.header.frame_id = 'base_link'
        status.control_source = RobotStatus.CONTROL_REMOTE if remote else RobotStatus.CONTROL_AUTO
        status.stm32_link_ok = valid
        status.command_fresh = True
        status.wheel_odom_valid = valid
        status.imu_valid = valid
        status.remote_connected = remote
        status.remote_override = remote
        status.safety_permit = permit
        status.watchdog_healthy = valid
        status.fault_message = '' if valid and permit else 'mock safety precondition is false'
        status.battery_voltage = 24.0
        status.battery_percent = 80.0
        if bool(self.get_parameter('publish_robot_status').value):
            self.status_pub.publish(status)

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        self.odom_pub.publish(odom)
        self.filtered_pub.publish(odom)
        imu = Imu()
        imu.header.stamp = now
        imu.header.frame_id = 'imu_link'
        imu.orientation.w = 1.0
        self.imu_pub.publish(imu)
        scan = LaserScan()
        scan.header.stamp = now
        scan.header.frame_id = 'laser_frame'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.15
        scan.range_max = 12.0
        scan.ranges = [5.0] * 361
        if bool(self.get_parameter('publish_scan').value):
            self.scan_pub.publish(scan)

        for parent, child in [('map', 'odom'), ('odom', 'base_link')]:
            transform = TransformStamped()
            transform.header.stamp = now
            transform.header.frame_id = parent
            transform.child_frame_id = child
            transform.transform.rotation.w = 1.0
            self.tf.sendTransform(transform)

    def publish_diagnostics(self):
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        state = DiagnosticStatus()
        state.name = 'HomeRobot/MockSystem'
        state.level = DiagnosticStatus.OK
        state.message = 'ROS-only simulation; no hardware transport and no velocity publisher'
        state.values = [KeyValue(key='hardware_connected', value='false'),
                        KeyValue(key='velocity_published', value='false')]
        msg.status = [state]
        self.diag_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockSystem()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
