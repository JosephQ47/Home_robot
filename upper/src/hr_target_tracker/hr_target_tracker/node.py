"""Fail-closed camera/HMMD target association. It never publishes velocity."""
import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from hr_interfaces.msg import FollowTarget, HmmdDetection, TrackerPolicy
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, LaserScan
from vision_msgs.msg import Detection2DArray


class TargetTracker(Node):
    def __init__(self):
        super().__init__('hr_target_tracker')
        self.declare_parameter('association_mode', 'disabled')
        self.declare_parameter('max_age_sec', 0.5)
        self.declare_parameter('minimum_confidence', 0.5)
        self.declare_parameter('image_width_px', 0.0)
        self.declare_parameter('horizontal_fov_rad', 0.0)
        self.declare_parameter('hmmd_supported_class', 'person')
        self.policy = None
        self.camera = None; self.camera_time = 0.0
        self.detections = None; self.detection_time = 0.0
        self.hmmd = None; self.hmmd_time = 0.0
        self.scan_time = 0.0
        self.pub = self.create_publisher(FollowTarget, '/follow_target', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(TrackerPolicy, '/task/tracker_policy', self.on_policy, 10)
        self.create_subscription(CameraInfo, '/camera/camera_info', self.on_camera, 10)
        self.create_subscription(Detection2DArray, '/detections', self.on_detection, 10)
        self.create_subscription(HmmdDetection, '/hmmd/detection', self.on_hmmd, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.create_timer(0.1, self.publish_state)

    def on_policy(self, msg): self.policy = msg
    def on_camera(self, msg): self.camera, self.camera_time = msg, time.monotonic()
    def on_detection(self, msg): self.detections, self.detection_time = msg, time.monotonic()
    def on_hmmd(self, msg): self.hmmd, self.hmmd_time = msg, time.monotonic()
    def on_scan(self, _msg): self.scan_time = time.monotonic()

    def fresh(self, stamp):
        return stamp > 0 and time.monotonic() - stamp <= float(self.get_parameter('max_age_sec').value)

    def bearing(self, pixel_x):
        if self.fresh(self.camera_time) and self.camera and self.camera.k[0] > 0:
            return -math.atan2(pixel_x - self.camera.k[2], self.camera.k[0])
        width = float(self.get_parameter('image_width_px').value)
        hfov = float(self.get_parameter('horizontal_fov_rad').value)
        if width > 0 and hfov > 0:
            return -(pixel_x - width / 2.0) / (width / 2.0) * hfov / 2.0
        return None

    def matching(self):
        if not self.detections or not self.policy:
            return []
        result = []
        threshold = float(self.get_parameter('minimum_confidence').value)
        for detection in self.detections.detections:
            if not detection.results:
                continue
            best = max(detection.results, key=lambda item: item.hypothesis.score)
            if (best.hypothesis.class_id == self.policy.target_class and
                    best.hypothesis.score >= threshold):
                result.append((detection, best.hypothesis.score))
        return result

    def evaluate(self):
        mode = str(self.get_parameter('association_mode').value)
        if mode == 'camera_laserscan':
            if not self.fresh(self.scan_time): return None, 'laser_scan_missing_or_stale'
            return None, 'camera_laserscan_extrinsics_and_association_TBD'
        if mode != 'person_hmmd': return None, 'association_disabled'
        if self.policy is None or not self.policy.enabled: return None, 'tracker_disabled'
        if not self.fresh(self.detection_time): return None, 'detections_missing_or_stale'
        if self.policy.target_class != str(self.get_parameter('hmmd_supported_class').value):
            return None, 'target_class_has_no_range_source'
        matches = self.matching()
        if not matches: return None, 'target_not_detected'
        if len(matches) != 1: return None, 'multiple_targets_hmmd_association_ambiguous'
        if not self.fresh(self.hmmd_time): return None, 'hmmd_missing_or_stale'
        if not self.hmmd.presence: return None, 'hmmd_no_person'
        if not self.hmmd.valid or not math.isfinite(self.hmmd.range_m):
            return None, 'hmmd_range_not_calibrated'
        detection, score = matches[0]
        bearing = self.bearing(detection.bbox.center.position.x)
        if bearing is None: return None, 'camera_intrinsics_or_fov_missing'
        target = FollowTarget(); target.header.stamp = self.get_clock().now().to_msg()
        target.header.frame_id = 'base_link'; target.state = FollowTarget.ASSOCIATED
        target.target_id = 'single-visible-person'; target.class_name = self.policy.target_class
        target.confidence = float(score); target.radar_associated = True
        target.range_m = self.hmmd.range_m; target.bearing_rad = bearing
        target.position_base.x = target.range_m * math.cos(bearing)
        target.position_base.y = target.range_m * math.sin(bearing)
        target.follow_allowed = True
        target.reason = 'single visual person weakly associated with HMMD range'
        return target, target.reason

    def publish_state(self):
        target, reason = self.evaluate()
        if target is None:
            target = FollowTarget(); target.header.stamp = self.get_clock().now().to_msg()
            target.header.frame_id = 'base_link'; target.state = FollowTarget.INVALID
            target.follow_allowed = False; target.radar_associated = False; target.reason = reason
        self.pub.publish(target)
        diag = DiagnosticArray(); diag.header.stamp = target.header.stamp
        status = DiagnosticStatus(); status.name = 'HomeRobot/TargetTracker'
        status.level = DiagnosticStatus.OK if target.follow_allowed else DiagnosticStatus.WARN
        status.message = target.reason; diag.status = [status]; self.diag.publish(diag)


def main(args=None):
    rclpy.init(args=args); node = TargetTracker()
    try: rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException): pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
