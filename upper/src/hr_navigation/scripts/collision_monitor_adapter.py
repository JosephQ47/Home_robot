#!/usr/bin/env python3
"""Small fail-closed Collision Monitor stand-in for ROS-only chain validation.

障碍源有两种，由 obstacle_source 参数选择：

  scan  （默认）二维激光扫描 /scan。技术方案 §3.5 的正式方案。
  hmmd  微雪 HMMD 毫米波 /hmmd/detection。**只在没有激光雷达时临时替代。**

⚠️ hmmd 模式的能力边界，必须清楚：
   这颗雷达是**人体微动**雷达。它看得见走动的人，**看不见墙、桌腿、椅子**——
   官方明确「纯静止不支持」「无法确保检测非人体移动物体」。所以 hmmd 模式
   **不是避障**，只是「有人靠得太近就停」。用它跑车必须在清空的场地，
   且人在旁边随时能断电。

   这里刻意**不**把 HMMD 的单个距离值合成假的 LaserScan。那样 Nav2 和代价地图
   会「看起来能跑」，但整张代价地图建立在不存在的观测上，比明着跑不起来危险。
"""
import math
import time
from geometry_msgs.msg import Twist
from hr_interfaces.msg import HmmdDetection
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ValidationCollisionMonitor(Node):
    def __init__(self):
        super().__init__('collision_monitor')
        self.declare_parameter('output_enabled', False)
        self.declare_parameter('obstacle_source', 'scan')
        self.declare_parameter('stop_distance_m', 0.40)
        self.declare_parameter('scan_timeout_sec', 0.30)
        self.declare_parameter('command_timeout_sec', 0.20)
        self.declare_parameter('max_linear_mps', 0.10)
        self.declare_parameter('max_angular_rps', 0.30)
        if not bool(self.get_parameter('output_enabled').value):
            raise RuntimeError('validation collision monitor requires output_enabled=true')
        if float(self.get_parameter('stop_distance_m').value) <= 0.0:
            raise RuntimeError('stop_distance_m must be positive')
        self.source = str(self.get_parameter('obstacle_source').value)
        if self.source not in ('scan', 'hmmd'):
            raise RuntimeError(f"obstacle_source must be 'scan' or 'hmmd', got {self.source!r}")
        self.last_scan_time = 0.0
        self.scan_clear = False
        self.last_cmd_time = 0.0
        self.last_cmd = Twist()
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Twist, '/cmd_vel_auto', self.on_command, 10)
        if self.source == 'scan':
            self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        else:
            self.create_subscription(HmmdDetection, '/hmmd/detection', self.on_hmmd, 10)
            # 每次启动都吼一遍。这条能力边界写在文档里没人看，写在启动日志里躲不掉。
            self.get_logger().warn(
                'obstacle_source=hmmd —— 毫米波只检测人体微动，'
                '看不见墙、家具等静止物体。这不是避障，只是「有人靠近就停」。'
                '必须在清空场地内低速运行，且人在旁边随时能断电。')
        self.create_timer(0.02, self.tick)

    def on_command(self, msg):
        self.last_cmd = msg
        self.last_cmd_time = time.monotonic()

    def on_hmmd(self, msg):
        """毫米波判「前方有人且太近」。

        失效安全同 scan 分支：距离不可用（range_m 为 NaN，即未标定）时一律判为
        不通行。宁可停着不动，也不能因为读不到距离就当成安全。
        """
        stop = float(self.get_parameter('stop_distance_m').value)
        if not msg.presence:
            self.scan_clear = True
        elif not math.isfinite(msg.range_m):
            self.scan_clear = False
        else:
            self.scan_clear = msg.range_m > stop
        self.last_scan_time = time.monotonic()

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
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
