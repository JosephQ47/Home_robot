"""Publishes /obstacle/depth_points: Gemini 2 cloud minus ground, minus junk.

Feeds the Nav2 local costmap as an auxiliary observation source only. It is
deliberately not wired into the Collision Monitor, whose stop zone stays on the
S3 /scan alone.

# @spec 家庭服务机器人技术方案.md#3.2
"""
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2

from .gating import GateConfig, gate_frame


class DepthObstacleNode(Node):
    def __init__(self):
        super().__init__('hr_depth_obstacle')
        for name, default in (('cloud_timeout_ms', 300), ('min_valid_ratio', 0.30),
                              ('min_range_m', 0.20), ('max_range_m', 4.00),
                              ('ground_height_m', 0.0), ('ground_tolerance_m', 0.03),
                              ('obstacle_min_height_m', 0.05), ('obstacle_max_height_m', 1.20)):
            self.declare_parameter(name, default)
        self.config = GateConfig(
            cloud_timeout_sec=int(self.get_parameter('cloud_timeout_ms').value) / 1000.0,
            min_valid_ratio=float(self.get_parameter('min_valid_ratio').value),
            min_range_m=float(self.get_parameter('min_range_m').value),
            max_range_m=float(self.get_parameter('max_range_m').value),
            ground_height_m=float(self.get_parameter('ground_height_m').value),
            ground_tolerance_m=float(self.get_parameter('ground_tolerance_m').value),
            obstacle_min_height_m=float(self.get_parameter('obstacle_min_height_m').value),
            obstacle_max_height_m=float(self.get_parameter('obstacle_max_height_m').value))
        self.last_reason = 'no_cloud'
        self.last_kept = 0
        self.pub = self.create_publisher(PointCloud2, '/obstacle/depth_points', 5)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(PointCloud2, '/camera/depth/points', self.on_cloud, 5)
        self.create_timer(1.0, self.publish_diagnostics)

    def on_cloud(self, msg):
        raw = list(pc2.read_points(msg, field_names=('x', 'y', 'z'), skip_nans=False))
        total = len(raw)
        finite = [(float(x), float(y), float(z)) for x, y, z in raw
                  if x == x and y == y and z == z]
        result = gate_frame(finite, total, len(finite), time.monotonic(),
                            time.monotonic(), self.config)
        self.last_reason = result.reason
        if not result.accepted:
            # DO-1/DO-2: publish nothing rather than something misleading.
            self.last_kept = 0
            return
        self.last_kept = len(result.points)
        self.pub.publish(pc2.create_cloud_xyz32(msg.header, list(result.points)))

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_depth_obstacle', hardware_id='gemini2')
        status.level = DiagnosticStatus.OK if self.last_reason == 'ok' else DiagnosticStatus.WARN
        status.message = self.last_reason
        status.values = [KeyValue(key='points_published', value=str(self.last_kept))]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    node = DepthObstacleNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
