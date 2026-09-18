"""hr_dock_pose_adapter: AprilTag sightings -> /detected_dock_pose.

Consumes apriltag_ros output from the Gemini 2 RGB stream and publishes the pose
OpenNav Docking should drive to. It publishes no charging state and makes no
claim of success: charging is confirmed only by sustained current or a verified
BMS state on /battery_state.

Note on where the pose comes from. apriltag_msgs/AprilTagDetection carries only
pixel geometry — family, id, decision margin, corners, homography — and no pose
at all. apriltag_ros publishes the tag's 3D pose as a TF frame instead. So this
node reads the detection array to decide *whether* a tag is trustworthy, and
reads TF to find out *where* it is. Trying to pull a pose out of the detection
message throws, which is exactly what happened before the package was installed.

# @spec 家庭服务机器人技术方案.md#3.1.4
"""
import math
import time

from apriltag_msgs.msg import AprilTagDetectionArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from tf2_ros import Buffer, LookupException, TransformListener

from .adapter import DockConfig, DockPoseAdapter, Pose2D, Rejected


def yaw_from_quaternion(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class DockPoseAdapterNode(Node):
    def __init__(self):
        super().__init__('hr_dock_pose_adapter')
        self.declare_parameter('dock_id', 'home_dock')
        self.declare_parameter('tag_id', 0)
        self.declare_parameter('tag_family', 'tag36h11')
        # apriltag_ros names each tag frame after its family and id by default.
        self.declare_parameter('tag_frame_template', '{family}:{id}')
        self.declare_parameter('tag_to_contact_xyyaw', [0.0, 0.0, 0.0])
        self.declare_parameter('tag_timeout_ms', 500)
        self.declare_parameter('max_jump_xy_m', 0.15)
        self.declare_parameter('max_jump_yaw_rad', 0.35)
        self.declare_parameter('max_consecutive_jumps', 3)
        self.declare_parameter('min_consecutive_detections', 3)
        self.declare_parameter('min_decision_margin', 30.0)
        self.declare_parameter('max_hamming', 0)
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
            min_consecutive_detections=int(
                self.get_parameter('min_consecutive_detections').value)))
        self.tag_frame = str(self.get_parameter('tag_frame_template').value).format(
            family=str(self.get_parameter('tag_family').value),
            id=self.adapter.config.tag_id)
        self.camera_info_valid = False
        self.last_reason = 'no_detection'
        self.rejected_ids = 0

        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.pub = self.create_publisher(PoseStamped, '/detected_dock_pose', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/docking/tag_status', 10)
        self.create_subscription(AprilTagDetectionArray, '/detections',
                                 self.on_detections, 10)
        self.create_subscription(CameraInfo, '/camera/color/camera_info', self.on_info, 10)
        self.create_timer(0.1, self.tick)
        self.create_timer(1.0, self.publish_diagnostics)
        self.get_logger().info(
            f'watching tag frame "{self.tag_frame}" for dock '
            f'"{self.adapter.config.dock_id}"')

    def on_info(self, msg):
        # DOCK-4: an uncalibrated camera yields a meaningless tag pose.
        self.camera_info_valid = any(v != 0.0 for v in msg.k)

    def usable(self, detection) -> bool:
        """Pixel-level gates, before TF is consulted at all."""
        if detection.id != self.adapter.config.tag_id:
            return False
        if detection.family != str(self.get_parameter('tag_family').value):
            return False
        if detection.hamming > int(self.get_parameter('max_hamming').value):
            return False
        return detection.decision_margin >= float(
            self.get_parameter('min_decision_margin').value)

    def on_detections(self, msg):
        now = time.monotonic()
        wanted = [d for d in msg.detections if self.usable(d)]
        if not wanted:
            # DOCK-1: count the sightings we deliberately threw away, so a
            # mis-set tag id shows up as a number rather than as silence.
            if msg.detections:
                self.rejected_ids += 1
                self.last_reason = 'tag_id_mismatch'
            return
        frame = str(self.get_parameter('dock_frame_id').value)
        try:
            tf = self.buffer.lookup_transform(frame, self.tag_frame,
                                              rclpy.time.Time())
        except (LookupException, Exception) as exc:  # noqa: BLE001
            # No transform means no pose. It never means "use the previous one".
            self.last_reason = f'tf_unavailable:{type(exc).__name__}'
            return
        # tf2's buffer keeps transforms for its whole cache duration, and asking
        # for "latest available" happily hands back a transform from ten seconds
        # ago after the broadcaster has stopped. Check the transform's own stamp:
        # a camera that stopped seeing the tag must produce no pose, not an old one.
        age = (self.get_clock().now() - rclpy.time.Time.from_msg(tf.header.stamp))
        if age.nanoseconds / 1e9 > self.adapter.config.tag_timeout_sec:
            self.last_reason = 'tf_stale'
            return
        t = tf.transform.translation
        pose = Pose2D(t.x, t.y, yaw_from_quaternion(tf.transform.rotation))
        out = self.adapter.update(wanted[0].id, pose, now, self.camera_info_valid)
        if isinstance(out, Rejected):
            self.last_reason = out.reason
            return
        self.last_reason = 'tracking'
        self.publish_pose(out, frame)

    def publish_pose(self, pose, frame):
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = frame
        msg.pose.position.x, msg.pose.position.y = pose.x, pose.y
        msg.pose.orientation.z = math.sin(pose.yaw / 2.0)
        msg.pose.orientation.w = math.cos(pose.yaw / 2.0)
        self.pub.publish(msg)

    def tick(self):
        # DOCK-2: simply stop publishing. Never emit a held-over pose.
        now = time.monotonic()
        if self.adapter.expired(now):
            self.adapter.tick(now)
            if self.last_reason == 'tracking':
                self.last_reason = 'tag_expired'

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_dock_pose_adapter', hardware_id='gemini2')
        status.level = (DiagnosticStatus.OK if self.last_reason == 'tracking'
                        else DiagnosticStatus.WARN)
        if self.adapter.failed:
            status.level = DiagnosticStatus.ERROR
        status.message = self.last_reason
        status.values = [
            KeyValue(key='dock_id', value=self.adapter.config.dock_id),
            KeyValue(key='tag_frame', value=self.tag_frame),
            KeyValue(key='camera_info_valid', value=str(self.camera_info_valid)),
            KeyValue(key='rejected_detections', value=str(self.rejected_ids)),
            KeyValue(key='latched_failure', value=str(self.adapter.failed)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = DockPoseAdapterNode()
    except RuntimeError as exc:
        print(f'hr_dock_pose_adapter: {exc}')
        rclpy.shutdown()
        raise SystemExit(1)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
