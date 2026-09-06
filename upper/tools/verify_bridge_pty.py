#!/usr/bin/env python3
"""Byte-level hr_bridge test using a pseudo-terminal, never real hardware."""
import fcntl
import os
import pty
import signal
import struct
import subprocess
import time

from geometry_msgs.msg import Twist
from hr_bridge.protocol import ID_STATE, ID_VELOCITY, Parser
from hr_interfaces.msg import RobotStatus
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


def checksum(data):
    return sum(data) & 0xFF


def state_frame():
    payload = struct.pack('>hhhhhhhhhh', 0, 0, 0, 0, 0, 0, 0, 0, 0, 1143)
    body = b'\xaa\x55' + bytes((25, ID_STATE)) + payload
    return body + bytes((checksum(body),))


def wait_until(node, predicate, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.03)
        if predicate():
            return True
    return False


def read_frames(master, parser):
    try:
        data = os.read(master, 4096)
    except BlockingIOError:
        return []
    return parser.feed(data)


class Probe(Node):
    def __init__(self):
        super().__init__('verify_bridge_pty')
        self.status = None
        self.odom = None
        self.create_subscription(RobotStatus, '/robot_status', self._status, 10)
        sensor_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(Odometry, '/wheel/odom_raw', self._odom, sensor_qos)
        self.command = self.create_publisher(Twist, '/cmd_vel', 10)

    def _status(self, msg):
        self.status = msg

    def _odom(self, msg):
        self.odom = msg


def main():
    domain = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '67')
    os.environ['ROS_DOMAIN_ID'] = domain
    env = os.environ.copy()
    master, slave = pty.openpty()
    slave_path = os.ttyname(slave)
    os.close(slave)
    flags = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    prefix = subprocess.check_output(
        ['ros2', 'pkg', 'prefix', 'hr_bridge'], env=env, text=True).strip()
    executable = os.path.join(prefix, 'lib', 'hr_bridge', 'hr_bridge')
    command = [
        executable, '--ros-args',
        '-p', f'port:={slave_path}', '-p', 'transport_enabled:=true',
        '-p', 'command_output_enabled:=true',
        '-p', 'legacy_firmware_watchdog_verified:=true',
        '-p', 'bench_motion_authorized:=true',
        '-p', 'command_timeout:=0.25', '-p', 'max_linear_mps:=0.10',
        '-p', 'max_angular_rps:=0.30',
    ]
    bridge = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, start_new_session=True)
    rclpy.init()
    node = Probe()
    parser = Parser()
    try:
        if not wait_until(node, lambda: 'hr_bridge' in node.get_node_names()):
            raise RuntimeError('hr_bridge did not start on pseudo-terminal')
        for _ in range(5):
            os.write(master, state_frame())
            rclpy.spin_once(node, timeout_sec=0.05)
        if not wait_until(node, lambda: node.odom is not None and node.status is not None):
            raise RuntimeError('state bytes did not reach ROS topics')
        if not (node.status.stm32_link_ok and node.status.safety_permit and
                node.status.watchdog_healthy):
            raise RuntimeError('explicit legacy bench gates did not become ready')
        if abs(node.status.battery_voltage - 11.43) > 0.01:
            raise RuntimeError('state payload was decoded incorrectly')

        requested = Twist()
        requested.linear.x = 1.0
        requested.angular.z = 2.0
        seen_nonzero = False
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not seen_nonzero:
            node.command.publish(requested)
            rclpy.spin_once(node, timeout_sec=0.03)
            for frame in read_frames(master, parser):
                if frame[3] != ID_VELOCITY:
                    continue
                values = struct.unpack('>hhh', frame[4:-1])
                if values != (0, 0, 0):
                    if values != (100, 0, 300):
                        raise RuntimeError(f'bridge limit mismatch: {values}')
                    seen_nonzero = True
        if not seen_nonzero:
            raise RuntimeError('ROS command did not become a serial velocity frame')

        saw_timeout_zero = False
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.03)
            for frame in read_frames(master, parser):
                if frame[3] == ID_VELOCITY and struct.unpack('>hhh', frame[4:-1]) == (0, 0, 0):
                    saw_timeout_zero = True
            if saw_timeout_zero and time.monotonic() > deadline - 0.5:
                break
        if not saw_timeout_zero:
            raise RuntimeError('stale command did not produce a zero serial frame')
        print('PASS: pseudo-UART state -> ROS, bounded command -> UART, timeout -> zero')
        print(f'SAFE: pseudo-terminal {slave_path}; no /dev/ttyACM device opened')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        bridge.send_signal(signal.SIGINT)
        try:
            output, _ = bridge.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(bridge.pid, signal.SIGKILL)
            output, _ = bridge.communicate()
        os.close(master)
        if bridge.returncode not in (0, 130, -signal.SIGINT):
            print(output)
            raise RuntimeError(f'bridge exited unexpectedly: {bridge.returncode}')


if __name__ == '__main__':
    main()
