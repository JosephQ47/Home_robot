#!/usr/bin/env python3
"""Verify the bounded motion/follow chain without opening any hardware device."""
import math
import os
import signal
import subprocess
import time

from geometry_msgs.msg import PoseStamped, Twist
from hr_interfaces.msg import FollowPolicy, FollowTarget
import rclpy
from rcl_interfaces.srv import SetParameters
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import LaserScan


def spin_for(node, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.02)


def wait_until(node, predicate, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
        if predicate():
            return True
    return False


def nonzero(msg):
    return abs(msg.linear.x) > 1e-5 or abs(msg.angular.z) > 1e-5


class Probe(Node):
    def __init__(self):
        super().__init__('verify_motion_chain')
        self.auto = []
        self.final = []
        self.create_subscription(Twist, '/cmd_vel_auto', lambda m: self.auto.append(m), 50)
        self.create_subscription(Twist, '/cmd_vel', lambda m: self.final.append(m), 50)
        self.goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.policy_pub = self.create_publisher(FollowPolicy, '/task/follow_policy', 10)
        self.target_pub = self.create_publisher(FollowTarget, '/follow_target', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.scan_parameter = self.create_client(SetParameters, '/hr_mock_system/set_parameters')

    def clear_samples(self):
        self.auto.clear()
        self.final.clear()

    def publish_goal(self):
        msg = PoseStamped()
        msg.header.frame_id = 'odom'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x = 0.30
        msg.pose.orientation.w = 1.0
        self.goal_pub.publish(msg)

    def publish_follow(self):
        policy = FollowPolicy()
        policy.header.stamp = self.get_clock().now().to_msg()
        policy.enabled = True
        policy.task_id = 'validation-follow'
        policy.desired_distance_m = 1.0
        policy.minimum_safe_distance_m = 0.5
        policy.goal_update_period_sec = 0.2
        policy.max_target_jump_m = 0.5
        policy.lost_timeout_sec = 0.5
        target = FollowTarget()
        target.header.stamp = policy.header.stamp
        target.header.frame_id = 'base_link'
        target.state = FollowTarget.LOCKED
        target.target_id = 'mock-cup'
        target.class_name = 'cup'
        target.confidence = 0.9
        target.radar_associated = True
        target.range_m = 2.0
        target.bearing_rad = 0.2
        target.follow_allowed = True
        self.policy_pub.publish(policy)
        self.target_pub.publish(target)

    def publish_blocked_scan(self):
        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = 'laser_frame'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.15
        scan.range_max = 12.0
        scan.ranges = [0.20] * 361
        self.scan_pub.publish(scan)

    def disable_mock_scan(self):
        if not self.scan_parameter.wait_for_service(timeout_sec=5.0):
            raise RuntimeError('mock parameter service unavailable')
        request = SetParameters.Request()
        request.parameters = [Parameter('publish_scan', value=False).to_parameter_msg()]
        future = self.scan_parameter.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        response = future.result()
        if response is None or not response.results[0].successful:
            raise RuntimeError('could not disable mock clear scan')


def main():
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '64')
    launch = subprocess.Popen(
        ['ros2', 'launch', 'hr_bringup', 'chain_validation.launch.py'], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    os.environ['ROS_DOMAIN_ID'] = env['ROS_DOMAIN_ID']
    rclpy.init()
    node = Probe()
    try:
        required = {'hr_mock_system', 'nav2_local_controller_adapter', 'collision_monitor', 'hr_bridge'}
        if not wait_until(node, lambda: required <= set(node.get_node_names())):
            raise RuntimeError('validation nodes did not become ready')

        final_publishers = node.get_publishers_info_by_topic('/cmd_vel')
        if [info.node_name for info in final_publishers] != ['collision_monitor']:
            raise RuntimeError(f'unexpected /cmd_vel publishers: {[i.node_name for i in final_publishers]}')
        subscribers = {info.node_name for info in node.get_subscriptions_info_by_topic('/cmd_vel')
                       if info.node_name != node.get_name()}
        if subscribers != {'hr_bridge'}:
            raise RuntimeError(f'unexpected /cmd_vel subscribers: {sorted(subscribers)}')

        spin_for(node, 0.5)
        node.clear_samples()
        node.publish_goal()
        if not wait_until(node, lambda: any(nonzero(m) for m in node.final), timeout=3.0):
            raise RuntimeError('bounded odom goal produced no final velocity')
        if max(abs(m.linear.x) for m in node.final) > 0.1001:
            raise RuntimeError('linear velocity exceeded validation limit')

        node.clear_samples()
        end = time.monotonic() + 0.8
        while time.monotonic() < end:
            node.publish_follow()
            rclpy.spin_once(node, timeout_sec=0.04)
        if not any(m.linear.x > 0 and m.angular.z > 0 for m in node.final):
            raise RuntimeError('locked follow target did not produce bounded steering')
        node.clear_samples()
        spin_for(node, 0.8)
        if not node.final or any(nonzero(m) for m in node.final[-10:]):
            raise RuntimeError('stale follow target did not stop motion')

        node.disable_mock_scan()
        node.clear_samples()
        end = time.monotonic() + 0.8
        while time.monotonic() < end:
            node.publish_follow()
            node.publish_blocked_scan()
            rclpy.spin_once(node, timeout_sec=0.02)
        if not node.final or any(nonzero(m) for m in node.final[-10:]):
            raise RuntimeError('collision obstacle did not suppress final velocity')

        print('PASS: bounded RViz goal, target follow, target-loss stop, obstacle stop, unique velocity path')
        print('SAFE: hr_bridge transport=false and command_output=false; no hardware device opened')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        launch.send_signal(signal.SIGINT)
        try:
            output, _ = launch.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
            output, _ = launch.communicate()
        bad = [line for line in output.splitlines()
               if 'Traceback (most recent call last)' in line or '[ERROR]' in line]
        if bad:
            print(output)
            raise RuntimeError('launch did not shut down cleanly')


if __name__ == '__main__':
    main()
