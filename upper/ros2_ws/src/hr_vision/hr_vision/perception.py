"""CPU YOLO adapter. No serial, velocity, navigation or distance outputs."""
import threading
import signal
import time
from pathlib import Path

import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from hr_interfaces.msg import PerceptionControl
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray

from .common import Latest, detections_message, diagnostic, fresh


class Perception(Node):
    def __init__(self):
        super().__init__('hr_perception')
        for key, value in {'model': '', 'classes': ['person', 'cup'], 'confidence': .35,
                           'image_size': 320, 'inference_hz': 2.0, 'max_age': 2.0,
                           'cpu_threads': 2, 'require_control': False}.items():
            self.declare_parameter(key, value)
        model_path = str(self.get_parameter('model').value)
        if not model_path or not Path(model_path).is_file():
            raise ValueError('model must be an existing local weight file; no implicit download')
        self.hz = float(self.get_parameter('inference_hz').value)
        self.max_age = float(self.get_parameter('max_age').value)
        if min(self.hz, self.max_age) <= 0:
            raise ValueError('inference_hz and max_age must be positive')
        import torch
        from ultralytics import YOLO
        torch.set_num_threads(max(1, int(self.get_parameter('cpu_threads').value)))
        self.model = YOLO(model_path)
        names = self.model.names
        requested = list(self.get_parameter('classes').value)
        missing = set(requested) - set(names.values())
        if missing:
            raise ValueError('classes absent from model: ' + ', '.join(sorted(missing)))
        self.class_ids = [i for i, name in names.items() if name in requested]
        self.bridge = CvBridge()
        self.frames, self.results = Latest(), Latest()
        self.stop = threading.Event()
        self.state = 'waiting for image'
        self.inference_ms = 0.
        self.published = 0
        self.consumed = 0
        self.invalid = False
        self.require_control = bool(self.get_parameter('require_control').value)
        self.enabled = not self.require_control
        self.pub = self.create_publisher(Detection2DArray, '/detections', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.sub = self.create_subscription(Image, '/camera/image_raw', self.on_image,
                                            qos_profile_sensor_data)
        self.control_sub = self.create_subscription(PerceptionControl, '/task/perception_control',
                                                    self.on_control, 10)
        self.create_timer(.05, self.publish_result)
        self.create_timer(1., self.publish_diagnostic)
        self.worker = threading.Thread(target=self.infer, daemon=True)
        self.worker.start()

    def on_image(self, msg):
        if not self.enabled:
            return
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        age = self.get_clock().now().nanoseconds * 1e-9 - stamp
        if not 0 <= age <= self.max_age:
            self.state = 'discarded stale or future-dated image'
            return
        self.frames.put((msg, time.monotonic(), age))

    def on_control(self, msg):
        self.enabled = msg.enabled or not self.require_control
        if not self.enabled:
            self.frames = Latest()
            self.results = Latest()
            self.state = 'disabled by task policy'

    def infer(self):
        last = 0
        while not self.stop.is_set():
            seq, item = self.frames.get()
            if item is None or seq == last:
                self.stop.wait(.02)
                continue
            last = seq
            msg, received, age = item
            if not fresh(received - age, self.max_age):
                continue
            started = time.monotonic()
            try:
                frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
                result = self.model.predict(frame, device='cpu', verbose=False,
                    imgsz=int(self.get_parameter('image_size').value),
                    conf=float(self.get_parameter('confidence').value), classes=self.class_ids)[0]
                rows = result.boxes.data.cpu().tolist()
                self.inference_ms = (time.monotonic() - started) * 1000
                output = detections_message(msg.header, rows, self.model.names, msg.width, msg.height)
                self.results.put((output, received - age))
                self.state = 'inference completed'
            except Exception as exc:
                self.state = 'inference error: ' + type(exc).__name__
            self.stop.wait(max(0., 1 / self.hz - (time.monotonic() - started)))

    def publish_result(self):
        seq, item = self.results.get()
        if item is not None and fresh(item[1], self.max_age):
            if seq != self.consumed:
                self.pub.publish(item[0])
                self.consumed = seq
                self.published += 1
                self.invalid = False
            return
        if not self.invalid:
            empty = Detection2DArray()
            empty.header.stamp = self.get_clock().now().to_msg()
            empty.header.frame_id = 'camera_optical_frame'
            self.pub.publish(empty)
            self.invalid = True

    def publish_diagnostic(self):
        diagnostic(self, self.diag, DiagnosticStatus.WARN if self.invalid or not self.enabled else DiagnosticStatus.OK,
                   'no fresh detection result' if self.invalid else self.state,
                   detail=self.state, inference_ms=round(self.inference_ms, 1),
                   published=self.published, backend='ultralytics_cpu')

    def destroy_node(self):
        self.stop.set()
        self.worker.join(timeout=10)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = Perception()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
