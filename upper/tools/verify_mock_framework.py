#!/usr/bin/env python3
"""End-to-end check for the safe ROS-only HomeRobot framework."""
import os
import signal
import subprocess
import time

from hr_interfaces.action import ExecuteTask
from hr_interfaces.msg import FollowTarget
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node


REQUIRED_TOPICS = {
    '/camera/image_raw', '/detections', '/diagnostics', '/follow_target', '/imu/data',
    '/odometry/filtered', '/robot_status', '/scan', '/task/status', '/wheel/odom_raw',
}


def wait_until(node, predicate, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
        if predicate(): return True
    return False


def main():
    test_domain = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '63')
    os.environ['ROS_DOMAIN_ID'] = test_domain
    launch_env = os.environ.copy()
    launch = subprocess.Popen(['ros2', 'launch', 'hr_bringup', 'mock.launch.py'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                              start_new_session=True, env=launch_env)
    rclpy.init(); node = Node('verify_mock_framework')
    target = {'message': None}
    node.create_subscription(FollowTarget, '/follow_target',
                             lambda msg: target.__setitem__('message', msg), 10)
    try:
        ready = wait_until(node, lambda: REQUIRED_TOPICS <= {name for name, _ in node.get_topic_names_and_types()})
        if not ready: raise RuntimeError('required mock topics did not appear')
        if node.get_publishers_info_by_topic('/cmd_vel') or node.get_publishers_info_by_topic('/cmd_vel_auto'):
            raise RuntimeError('mock mode has a velocity publisher')
        if not wait_until(node, lambda: target['message'] is not None):
            raise RuntimeError('no follow-target safety state received')
        if target['message'].follow_allowed:
            raise RuntimeError('uncalibrated mock tracker allowed following')
        client = ActionClient(node, ExecuteTask, '/task/execute')
        if not client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError('/task/execute unavailable')
        goal = ExecuteTask.Goal()
        goal.task_id, goal.source, goal.task_type = 'framework-check', 'TEST', 'observe'
        goal.map_id, goal.area_id, goal.target_class, goal.mode = 'mock', 'mock', 'person', 'observe'
        future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
        handle = future.result()
        if handle is None or not handle.accepted: raise RuntimeError('framework task rejected')
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=10.0)
        result = result_future.result()
        if result is None or not result.result.success:
            raise RuntimeError('framework task did not complete')
        print('PASS: mock topology, fail-closed tracker, no velocity publishers, task action')
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
        launch.send_signal(signal.SIGINT)
        try: launch.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
            launch.wait()


if __name__ == '__main__':
    main()
