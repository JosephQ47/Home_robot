import math
import threading
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose


class Latest:
    """A one-item mailbox: slow consumers never build a frame backlog."""
    def __init__(self):
        self.lock = threading.Lock()
        self.item = None
        self.sequence = 0

    def put(self, item):
        with self.lock:
            self.sequence += 1
            self.item = item

    def get(self):
        with self.lock:
            return self.sequence, self.item


def fresh(received, max_age, now=None):
    age = (time.monotonic() if now is None else now) - received
    return 0 <= age <= max_age


def detections_message(header, rows, names, width, height):
    message = Detection2DArray()
    message.header = header
    for x1, y1, x2, y2, score, class_id in rows:
        if not all(math.isfinite(float(v)) for v in (x1, y1, x2, y2, score, class_id)):
            continue
        x1, x2 = max(0., min(width, float(x1))), max(0., min(width, float(x2)))
        y1, y2 = max(0., min(height, float(y1))), max(0., min(height, float(y2)))
        if x2 <= x1 or y2 <= y1 or not 0 <= score <= 1:
            continue
        detection = Detection2D()
        detection.header = header
        detection.bbox.center.position.x = (x1 + x2) / 2
        detection.bbox.center.position.y = (y1 + y2) / 2
        detection.bbox.size_x = x2 - x1
        detection.bbox.size_y = y2 - y1
        hypothesis = ObjectHypothesisWithPose()
        hypothesis.hypothesis.class_id = str(names[int(class_id)])
        hypothesis.hypothesis.score = float(score)
        detection.results.append(hypothesis)
        message.detections.append(detection)
    return message


def diagnostic(node, publisher, level, message, **values):
    status = DiagnosticStatus(name=node.get_name(), level=level, message=message)
    status.values = [KeyValue(key=str(k), value=str(v)) for k, v in values.items()]
    array = DiagnosticArray()
    array.header.stamp = node.get_clock().now().to_msg()
    array.status = [status]
    publisher.publish(array)
