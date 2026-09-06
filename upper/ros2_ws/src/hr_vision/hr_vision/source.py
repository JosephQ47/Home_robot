"""Decode RTSP/files in a worker; publish only newly received frames."""
import os
import signal
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from .common import Latest, diagnostic, fresh


class ImageSource(Node):
    def __init__(self):
        super().__init__('hr_image_source')
        defaults = {'source': 'synthetic', 'publish_hz': 5.0, 'frame_id': 'camera_optical_frame',
                    'max_age': 2.0, 'loop': False, 'reconnect_seconds': 2.0,
                    'output_width': 640, 'capture_width': 0, 'capture_height': 0,
                    'capture_fps': 0.0, 'pixel_format': ''}
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        self.source = str(self.get_parameter('source').value)
        self.hz = float(self.get_parameter('publish_hz').value)
        self.max_age = float(self.get_parameter('max_age').value)
        self.retry = float(self.get_parameter('reconnect_seconds').value)
        self.output_width = int(self.get_parameter('output_width').value)
        self.capture_width = int(self.get_parameter('capture_width').value)
        self.capture_height = int(self.get_parameter('capture_height').value)
        self.capture_fps = float(self.get_parameter('capture_fps').value)
        self.pixel_format = str(self.get_parameter('pixel_format').value).strip().upper()
        if min(self.hz, self.max_age, self.retry) <= 0 or self.output_width < 0:
            raise ValueError('publish_hz, max_age and reconnect_seconds must be positive; output_width must be >= 0')
        self.bridge = CvBridge()
        self.frames = Latest()
        self.stop = threading.Event()
        self.status = 'waiting for source'
        self.last_sequence = 0
        self.count = 0
        self.started = time.monotonic()
        self.pub = self.create_publisher(Image, '/camera/image_raw', qos_profile_sensor_data)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_timer(1 / self.hz, self.publish_frame)
        self.create_timer(1., self.publish_diagnostic)
        self.worker = threading.Thread(target=self.capture, daemon=True)
        self.worker.start()

    def capture(self):
        cap = None
        try:
            is_rtsp = self.source.lower().startswith(('rtsp://', 'rtsps://'))
            still = Path(self.source).suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')
            is_v4l2 = self.source.startswith('/dev/video') or self.source.isdigit()
            capture_source = int(self.source) if self.source.isdigit() else self.source
            os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')
            while not self.stop.is_set():
                if self.source == 'synthetic':
                    frame = np.zeros((360, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, 'TRANSPORT TEST - NO REAL CAMERA', (10, 180),
                                cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 1)
                elif still:
                    frame = cv2.imread(self.source)
                    if frame is None:
                        self.status = 'cannot read image file'
                        self.stop.wait(self.retry)
                        continue
                else:
                    if cap is None:
                        self.status = 'opening source'
                        if is_v4l2:
                            cap = cv2.VideoCapture(capture_source, cv2.CAP_V4L2)
                            if self.pixel_format:
                                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.pixel_format[:4]))
                            if self.capture_width > 0:
                                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
                            if self.capture_height > 0:
                                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
                            if self.capture_fps > 0:
                                cap.set(cv2.CAP_PROP_FPS, self.capture_fps)
                        else:
                            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG, [
                                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
                                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
                    ok, frame = cap.read()
                    if not ok:
                        cap.release()
                        cap = None
                        self.status = 'source disconnected or EOF'
                        if not is_rtsp and not is_v4l2 and not self.get_parameter('loop').value:
                            return
                        self.stop.wait(self.retry)
                        continue
                if self.output_width > 0 and frame.shape[1] > self.output_width:
                    height = max(1, round(frame.shape[0] * self.output_width / frame.shape[1]))
                    frame = cv2.resize(frame, (self.output_width, height), interpolation=cv2.INTER_AREA)
                self.frames.put((frame, time.monotonic(), self.get_clock().now().to_msg()))
                self.status = 'receiving'
                # Network sources must be drained; pace files and generated frames.
                if not is_rtsp:
                    self.stop.wait(1 / self.hz)
        except Exception as exc:
            # Do not log a URI which may contain credentials.
            self.status = 'capture error: ' + type(exc).__name__
        finally:
            if cap is not None:
                cap.release()

    def publish_frame(self):
        sequence, item = self.frames.get()
        if item is None or sequence == self.last_sequence or not fresh(item[1], self.max_age):
            return
        frame, _, stamp = item
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = stamp  # Decode receipt time, not sensor exposure time.
        msg.header.frame_id = self.get_parameter('frame_id').value
        self.pub.publish(msg)
        self.last_sequence = sequence
        self.count += 1

    def publish_diagnostic(self):
        _, item = self.frames.get()
        valid = item is not None and fresh(item[1], self.max_age)
        diagnostic(self, self.diag, DiagnosticStatus.OK if valid else DiagnosticStatus.WARN,
                   self.status, frames=self.count,
                   average_publish_fps=round(self.count / max(.001, time.monotonic()-self.started), 2),
                   timestamp_source='decoder receipt', calibrated=False)

    def destroy_node(self):
        self.stop.set()
        self.worker.join(timeout=7)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ImageSource()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
