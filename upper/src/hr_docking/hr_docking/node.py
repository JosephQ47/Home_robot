"""hr_dock_pose_adapter: AprilTag sightings -> /detected_dock_pose.

Consumes apriltag_ros detections from the Gemini 2 RGB stream and publishes the
pose OpenNav Docking should drive to. It publishes no charging state and makes
no claim of success: charging is confirmed only by sustained current or a
verified BMS state on /battery_state.

# @spec 家庭服务机器人技术方案.md#3.1.4
"""
import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo

from .adapter import DockConfig, DockPoseAdapter, Pose2D, Rejected

try:
    from apriltag_msgs.msg import AprilTagDetectionArray
except ImportError:  # pragma: no cover - apriltag_ros is an optional runtime dep
    AprilTagDetectionArray = None


def yaw_from_quaternion(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class DockPoseAdapterNode(Node):
    def __init__(self):
        super().__init__('hr_dock_pose_adapter')
        if AprilTagDetectionArray is None:
            raise RuntimeError('apriltag_msgs is not installed; install apriltag_ros first')
        self.declare_parameter('dock_id', 'home_dock')
        self.declare_parameter('tag_id', 0)
        self.declare_parameter('tag_to_contact_xyyaw', [0.0, 0.0, 0.0])
        self.declare_parameter('tag_timeout_ms', 500)
        self.declare_parameter('max_jump_xy_m', 0.15)
        self.declare_parameter('max_jump_yaw_rad', 0.35)
        self.declare_parameter('max_consecutive_jumps', 3)
        self.declare_parameter('min_consecutive_detections', 3)
        self.declare_parameter('dock_frame_id', 'odom')
        offset = list(self.get_parameter('tag_to_contact_xyyaw').value)
        if len(offset) != 3:
            raise RuntimeError('tag_to_contact_xyyaw must be [x, y, yaw]')
        self.adapter = DockPoseAdapter(DockConfig(
            dock_id=str(self.get_parameter('dock_id').value),
            tag_id=int(self.get_parameter('tag_id').value),
            tag_to_contact=Pose2D(*[float(v) for v in offset]),
            tag_timeout_sec=int(self.get_parameter('tag_timeout_ms').value) / 1000.0,
            max_jump_xy_m=float(self.get_parameter('max_jump_xy_m').value),
            max_jump_yaw_rad=float(self.get_parameter('max_jump_yaw_rad').value),
            max_consecutive_jumps=int(self.get_parameter('max_consecutive_jumps').value),
            min_consecutive_detections=int(self.get_parameter('min_consecutive_detections').value)))
        self.camera_info_valid = False
        self.last_reason = 'no_detection'
        self.pub = self.create_publisher(PoseStamped, '/detected_dock_pose', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/docking/tag_status', 10)
        self.create_subscription(AprilTagDetectionArray, '/detections/apriltag',
                                 self.on_detections, 10)
        self.create_subscription(CameraInfo, '/camera/color/camera_info', self.on_info, 10)
        self.create_timer(0.1, self.tick)
        self.create_timer(1.0, self.publish_diagnostics)

    def on_info(self, msg):
        # DOCK-4: an uncalibrated camera yields a meaningless tag pose.
        self.camera_info_valid = any(v != 0.0 for v in msg.k)

    def on_detections(self, msg):
        now = time.monotonic()
        for detection in msg.detections:
            pose = detection.pose.pose.pose
            out = self.adapter.update(
                int(detection.id), Pose2D(pose.position.x, pose.position.y,
                                          yaw_from_quaternion(pose.orientation)),
                now, self.camera_info_valid)
            if isinstance(out, Rejected):
                self.last_reason = out.reason
                continue
            self.last_reason = 'tracking'
            self.publish_pose(out)

    def publish_pose(self, pose):
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = str(self.get_parameter('dock_frame_id').value)
        msg.pose.position.x, msg.pose.position.y = pose.x, pose.y
        msg.pose.orientation.z = math.sin(pose.yaw / 2.0)
        msg.pose.orientation.w = math.cos(pose.yaw / 2.0)
        self.pub.publish(msg)

    def tick(self):
        # DOCK-2: simply stop publishing. Never emit a held-over pose.
        if self.adapter.expired(time.monotonic()):
            self.adapter.tick(time.monotonic())
            self.last_reason = 'tag_expired'

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_dock_pose_adapter', hardware_id='gemini2')
        status.level = DiagnosticStatus.OK if self.last_reason == 'tracking' else DiagnosticStatus.WARN
        if self.adapter.failed:
            status.level = DiagnosticStatus.ERROR
        status.message = self.last_reason
        status.values = [
            KeyValue(key='dock_id', value=self.adapter.config.dock_id),
            KeyValue(key='tag_id', value=str(self.adapter.config.tag_id)),
            KeyValue(key='camera_info_valid', value=str(self.camera_info_valid)),
            KeyValue(key='latched_failure', value=str(self.adapter.failed)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    node = DockPoseAdapterNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
