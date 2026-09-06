#!/usr/bin/env python3
"""Small fail-closed Collision Monitor stand-in for ROS-only chain validation."""
import math
import time
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ValidationCollisionMonitor(Node):
    def __init__(self):
        super().__init__('collision_monitor')
        self.declare_parameter('output_enabled', False)
        self.declare_parameter('stop_distance_m', 0.40)
        self.declare_parameter('scan_timeout_sec', 0.30)
        self.declare_parameter('command_timeout_sec', 0.20)
        self.declare_parameter('max_linear_mps', 0.10)
        self.declare_parameter('max_angular_rps', 0.30)
        if not bool(self.get_parameter('output_enabled').value):
            raise RuntimeError('validation collision monitor requires output_enabled=true')
        if float(self.get_parameter('stop_distance_m').value) <= 0.0:
            raise RuntimeError('stop_distance_m must be positive')
        self.last_scan_time = 0.0
        self.scan_clear = False
        self.last_cmd_time = 0.0
        self.last_cmd = Twist()
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Twist, '/cmd_vel_auto', self.on_command, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.create_timer(0.02, self.tick)

    def on_command(self, msg):
        self.last_cmd = msg
        self.last_cmd_time = time.monotonic()

    def on_scan(self, msg):
        stop = float(self.get_parameter('stop_distance_m').value)
        valid = [r for r in msg.ranges if math.isfinite(r) and msg.range_min <= r <= msg.range_max]
        self.scan_clear = bool(valid) and min(valid) > stop
        self.last_scan_time = time.monotonic()

    @staticmethod
    def clamp(value, limit):
        return max(-limit, min(limit, value))

    def tick(self):
        now = time.monotonic()
        scan_fresh = now - self.last_scan_time <= float(self.get_parameter('scan_timeout_sec').value)
        cmd_fresh = now - self.last_cmd_time <= float(self.get_parameter('command_timeout_sec').value)
        out = Twist()
        if scan_fresh and self.scan_clear and cmd_fresh:
            out.linear.x = self.clamp(self.last_cmd.linear.x, float(self.get_parameter('max_linear_mps').value))
            out.angular.z = self.clamp(self.last_cmd.angular.z, float(self.get_parameter('max_angular_rps').value))
        self.pub.publish(out)

    def destroy_node(self):
        if rclpy.ok(context=self.context):
            self.pub.publish(Twist())
        return super().destroy_node()


def main():
    rclpy.init()
    node = ValidationCollisionMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
