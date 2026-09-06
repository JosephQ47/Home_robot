#!/usr/bin/env python3
"""End-to-end goal-to-UART validation over a pseudo-terminal."""
import fcntl
import math
import os
import pty
import signal
import struct
import subprocess
import time

from geometry_msgs.msg import PoseStamped, Twist
from hr_bridge.protocol import ID_STATE, ID_VELOCITY, Parser
from hr_interfaces.msg import RobotStatus
from rcl_interfaces.srv import SetParameters
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import LaserScan


def frame_checksum(data):
    return sum(data) & 0xFF


def state_frame():
    payload = struct.pack('>hhhhhhhhhh', 0, 0, 0, 0, 0, 0, 0, 0, 0, 1143)
    body = b'\xaa\x55' + bytes((25, ID_STATE)) + payload
    return body + bytes((frame_checksum(body),))


class Probe(Node):
    def __init__(self):
        super().__init__('verify_full_control_pty')
        self.status = None
        self.goal = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.scan = self.create_publisher(LaserScan, '/scan', 10)
        self.create_subscription(RobotStatus, '/robot_status', self._status, 20)
        self.scan_params = self.create_client(SetParameters, '/hr_mock_system/set_parameters')

    def _status(self, msg):
        self.status = msg

    def set_mock_scan(self, enabled):
        if not self.scan_params.wait_for_service(timeout_sec=5.0):
            raise RuntimeError('mock parameter service unavailable')
        request = SetParameters.Request()
        request.parameters = [Parameter('publish_scan', value=enabled).to_parameter_msg()]
        future = self.scan_params.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is None or not future.result().results[0].successful:
            raise RuntimeError('could not change mock scan source')

    def publish_goal(self):
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = 0.30
        goal.pose.orientation.w = 1.0
        self.goal.publish(goal)

    def publish_obstacle(self):
        scan = LaserScan()
        scan.header.frame_id = 'laser_frame'
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.15
        scan.range_max = 12.0
        scan.ranges = [0.20] * 361
        self.scan.publish(scan)


def read_velocity(master, parser):
    result = []
    try:
        data = os.read(master, 4096)
    except BlockingIOError:
        return result
    for frame in parser.feed(data):
        if frame[3] == ID_VELOCITY:
            result.append(struct.unpack('>hhh', frame[4:-1]))
    return result


def main():
    domain = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '68')
    os.environ['ROS_DOMAIN_ID'] = domain
    env = os.environ.copy()
    master, slave = pty.openpty()
    slave_path = os.ttyname(slave)
    os.close(slave)
    flags = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    launch = subprocess.Popen([
        'ros2', 'launch', 'hr_bringup', 'chain_validation.launch.py',
        f'bridge_port:={slave_path}', 'bridge_transport_enabled:=true',
        'bridge_command_output_enabled:=true',
        'legacy_firmware_watchdog_verified:=true', 'bench_motion_authorized:=true',
        'publish_mock_robot_status:=false',
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True)
    rclpy.init()
    node = Probe()
    parser = Parser()
    try:
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                os.write(master, state_frame())
            except OSError:
                pass
            rclpy.spin_once(node, timeout_sec=0.05)
            if node.status and node.status.safety_permit:
                break
        else:
            raise RuntimeError('bridge-backed RobotStatus did not become safe in PTY bench mode')

        publishers = [info.node_name for info in node.get_publishers_info_by_topic('/cmd_vel')]
        if publishers != ['collision_monitor']:
            raise RuntimeError(f'final velocity topology is not unique: {publishers}')

        # 目标必须持续重发，不能只发一次。
        # nav2_local_controller_adapter 的 tick() 在任何一次 safe() 为假时都会
        # 执行 self.goal = None —— 这是**正确的失效安全行为**，安全事件之后不该
        # 让旧目标自己复活。但它意味着：目标若恰好落在 /odometry/filtered 还没
        # 新鲜的那一刻（本测试里 RobotStatus 来自 PTY 桥，就绪时刻与 Mock 不同步），
        # 就会被立刻清掉，而只发一次的测试再也没有第二次机会。
        # 实测证据：节点日志显示门禁通过但 goal=False，且没有任何 'rejected' 日志
        # —— 目标既没被拒绝，也不在了，正是被 tick() 清掉的形状。
        nonzero = []
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not nonzero:
            node.publish_goal()
            os.write(master, state_frame())
            rclpy.spin_once(node, timeout_sec=0.03)
            nonzero.extend(value for value in read_velocity(master, parser) if value != (0, 0, 0))
        if not nonzero:
            raise RuntimeError('goal did not reach the UART byte stream')
        if any(abs(vx) > 100 or vy != 0 or abs(wz) > 300 for vx, vy, wz in nonzero):
            raise RuntimeError(f'UART output exceeded limits: {nonzero[-1]}')

        node.set_mock_scan(False)
        settled = []
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            os.write(master, state_frame())
            node.publish_obstacle()
            rclpy.spin_once(node, timeout_sec=0.02)
            settled.extend(read_velocity(master, parser))
        if len(settled) < 10 or any(value != (0, 0, 0) for value in settled[-10:]):
            raise RuntimeError('obstacle stop did not reach the UART byte stream')

        print('PASS: /goal_pose -> local controller -> collision monitor -> bridge -> UART bytes')
        print('PASS: obstacle -> zero UART frames; speed topology and limits enforced')
        print(f'SAFE: pseudo-terminal {slave_path}; real controller was not opened')
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
        os.close(master)
        if 'Traceback (most recent call last)' in output:
            print(output)
            raise RuntimeError('validation launch did not shut down cleanly')


if __name__ == '__main__':
    main()
