"""Wrist D435i perception: detections + depth -> grasp candidates.

Runs only while an arm task is active, so the D435i does not fight Gemini 2 for
USB bandwidth the rest of the time (技术方案 §3.12.6).

Every frame must clear four independent gates before it can produce a
candidate: the calibration must still describe this robot today, the camera
intrinsics must be real, the depth patch must be dense and consistent, and the
object must fit the gripper. Failing any of them publishes an empty candidate
list *with a reason* — never a stale candidate, and never an empty list that
could be mistaken for "nothing here".

# @spec 家庭服务机器人技术方案.md#3.12.3
"""
import datetime
import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from hr_interfaces.msg import GraspCandidate as GraspCandidateMsg
from hr_interfaces.msg import GraspCandidates
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool

from .calibration import CalibrationError, load
from .grasping import (CameraIntrinsics, DepthQuality, GraspCandidate,
                       ObjectGraspConfig, Rejected, best_candidate, plan_grasp)

try:
    from vision_msgs.msg import Detection2DArray
except ImportError:  # pragma: no cover - vision_msgs is an optional runtime dep
    Detection2DArray = None


def depth_patch(image: Image, u, v, w, h, stride=4):
    """Sample depths inside a bounding box, in metres.

    16UC1 is millimetres (RealSense default); 32FC1 is already metres.
    Anything else is refused rather than guessed at.
    """
    if image.encoding == '16UC1':
        scale, size, unpack = 0.001, 2, lambda b: b[0] | (b[1] << 8)
    elif image.encoding == '32FC1':
        import struct
        scale, size, unpack = 1.0, 4, lambda b: struct.unpack('<f', bytes(b))[0]
    else:
        return None
    u0, u1 = max(0, int(u - w / 2)), min(image.width, int(u + w / 2))
    v0, v1 = max(0, int(v - h / 2)), min(image.height, int(v + h / 2))
    out = []
    data = image.data
    for row in range(v0, v1, stride):
        base = row * image.step
        for col in range(u0, u1, stride):
            off = base + col * size
            if off + size <= len(data):
                out.append(unpack(data[off:off + size]) * scale)
    return out


class ArmPerceptionNode(Node):
    def __init__(self):
        super().__init__('hr_arm_perception')
        self.declare_parameter('hand_eye_calibration_file', '')
        self.declare_parameter('arm_serial', '')
        self.declare_parameter('camera_serial', '')
        self.declare_parameter('enable_only_during_arm_task', True)
        self.declare_parameter('depth_timeout_ms', 300)
        self.declare_parameter('min_depth_valid_ratio', 0.50)
        self.declare_parameter('min_depth_m', 0.15)
        self.declare_parameter('max_depth_m', 1.20)
        self.declare_parameter('max_depth_spread_m', 0.08)
        self.declare_parameter('accepted_object_classes', [''])
        self.declare_parameter('gripper_max_width_m', 0.09)
        self.declare_parameter('min_confidence', 0.70)

        if Detection2DArray is None:
            raise RuntimeError('vision_msgs is not installed; hr_arm_perception needs it')

        path = str(self.get_parameter('hand_eye_calibration_file').value)
        if not path:
            # ARM-2: grasping without a valid hand-eye calibration is refused, and
            # an absent calibration is just the strongest form of invalid.
            raise RuntimeError(
                'hr_arm_perception refuses to start without a hand-eye calibration '
                'file; see docs/features/hr_arm.md §3')
        try:
            self.calibration = load(path)
            self.calibration.check(str(self.get_parameter('arm_serial').value),
                                   str(self.get_parameter('camera_serial').value),
                                   datetime.date.today())
        except CalibrationError as exc:
            raise RuntimeError(f'hand-eye calibration rejected: {exc}') from exc
        self.get_logger().info(
            f'hand-eye calibration loaded: arm={self.calibration.arm_serial} '
            f'camera={self.calibration.camera_serial} '
            f'valid_until={self.calibration.valid_until} '
            f'mean_error={self.calibration.mean_error_m:.4f} m')

        self.quality = DepthQuality(
            min_valid_ratio=float(self.get_parameter('min_depth_valid_ratio').value),
            min_depth_m=float(self.get_parameter('min_depth_m').value),
            max_depth_m=float(self.get_parameter('max_depth_m').value),
            max_spread_m=float(self.get_parameter('max_depth_spread_m').value))
        self.classes = {c for c in self.get_parameter('accepted_object_classes').value if c}
        self.intrinsics = None
        self.depth = None
        self.depth_stamp = float('-inf')
        self.active = not bool(self.get_parameter('enable_only_during_arm_task').value)
        self.last_reason = 'idle'

        self.pub = self.create_publisher(GraspCandidates, '/arm/grasp_candidates', 5)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(CameraInfo, '/arm_camera/color/camera_info',
                                 self.on_info, 5)
        self.create_subscription(Image, '/arm_camera/aligned_depth_to_color/image_raw',
                                 self.on_depth, 5)
        self.create_subscription(Detection2DArray, '/arm/detections', self.on_detections, 5)
        self.create_subscription(Bool, '/arm/perception_enabled', self.on_enable, 5)
        self.create_timer(1.0, self.publish_diagnostics)

    def on_enable(self, msg):
        self.active = bool(msg.data)

    def on_info(self, msg):
        self.intrinsics = CameraIntrinsics(fx=msg.k[0], fy=msg.k[4], cx=msg.k[2], cy=msg.k[5])

    def on_depth(self, msg):
        self.depth, self.depth_stamp = msg, time.monotonic()

    def config_for(self, object_class):
        return ObjectGraspConfig(
            object_class=object_class,
            gripper_width_m=float(self.get_parameter('gripper_max_width_m').value) * 0.7,
            max_gripper_width_m=float(self.get_parameter('gripper_max_width_m').value),
            pregrasp_height_m=0.12, approach_distance_m=0.08, lift_height_m=0.10,
            min_confidence=float(self.get_parameter('min_confidence').value))

    def publish(self, header, candidates, reason, depth_ok):
        msg = GraspCandidates()
        msg.header = header
        msg.calibration_valid = True
        msg.depth_valid = depth_ok
        msg.reject_reason = reason
        for c in candidates:
            m = GraspCandidateMsg()
            m.object_class, m.confidence = c.object_class, float(c.confidence)
            # Hand-eye transform: camera optical frame -> the arm's own frame.
            x, y, z = self.calibration.tool0_to_camera.apply(c.position)
            m.position.x, m.position.y, m.position.z = x, y, z
            m.grasp_angle, m.gripper_width = float(c.grasp_angle), float(c.gripper_width)
            m.quality, m.depth_valid_ratio = float(c.quality), float(c.depth_valid_ratio)
            msg.candidates.append(m)
        self.pub.publish(msg)
        self.last_reason = reason or 'tracking'

    def on_detections(self, msg):
        if not self.active:
            return
        header = msg.header
        if self.intrinsics is None or not self.intrinsics.valid():
            self.publish(header, [], 'camera_info_missing', False)
            return
        if self.depth is None or \
                time.monotonic() - self.depth_stamp > \
                int(self.get_parameter('depth_timeout_ms').value) / 1000.0:
            # ARM-6: a stale depth frame must never back a fresh grasp.
            self.publish(header, [], 'depth_stale', False)
            return

        results, reasons = [], []
        for detection in msg.detections:
            if not detection.results:
                continue
            hypothesis = detection.results[0]
            object_class = getattr(hypothesis, 'id', '') or \
                getattr(getattr(hypothesis, 'hypothesis', None), 'class_id', '')
            score = getattr(hypothesis, 'score', 0.0) or \
                getattr(getattr(hypothesis, 'hypothesis', None), 'score', 0.0)
            if self.classes and object_class not in self.classes:
                reasons.append('class_not_accepted')
                continue
            bbox = (detection.bbox.center.x, detection.bbox.center.y,
                    detection.bbox.size_x, detection.bbox.size_y)
            samples = depth_patch(self.depth, *bbox)
            if samples is None:
                reasons.append(f'unsupported_depth_encoding:{self.depth.encoding}')
                continue
            out = plan_grasp(object_class, float(score), bbox, samples,
                             self.intrinsics, self.config_for(object_class), self.quality)
            if isinstance(out, Rejected):
                reasons.append(out.reason)
            else:
                results.append(out)

        best = best_candidate(results)
        if best is None:
            self.publish(header, [], reasons[0] if reasons else 'no_detection', True)
            return
        # SELECT_GRASP only ever gets the single best candidate: offering the arm
        # a menu would push the choice into a node that has less context.
        self.publish(header, [best], '', True)

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_arm_perception', hardware_id='d435i')
        status.level = (DiagnosticStatus.OK if self.last_reason == 'tracking'
                        else DiagnosticStatus.WARN)
        status.message = self.last_reason
        status.values = [
            KeyValue(key='active', value=str(self.active)),
            KeyValue(key='calibration_valid_until',
                     value=self.calibration.valid_until.isoformat()),
            KeyValue(key='intrinsics', value=str(self.intrinsics is not None)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ArmPerceptionNode()
    except RuntimeError as exc:
        print(f'hr_arm_perception: {exc}')
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
