"""相机侧共用的小工具。

技术方案 §9.2 没有共享工具包，本仓惯例是小工具各包自持
（fresh 在 hr_local_motion / hr_task_manager / hr_target_tracker 各有一份），
故此处与 hr_perception/common.py 各留一份，不新建方案外的包。
识别侧专用的 detections_message 不在这里。
"""
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


def diagnostic(node, publisher, level, message, **values):
    status = DiagnosticStatus(name=node.get_name(), level=level, message=message)
    status.values = [KeyValue(key=str(k), value=str(v)) for k, v in values.items()]
    array = DiagnosticArray()
    array.header.stamp = node.get_clock().now().to_msg()
    array.status = [status]
    publisher.publish(array)
