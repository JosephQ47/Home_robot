"""Wrist D435i perception for grasping. Skeleton: hardware not fitted.

Deliberately refuses to start rather than publishing placeholder poses — a
grasp candidate that is not backed by a real camera and a valid hand-eye
calibration is worse than no candidate at all.

# @spec 家庭服务机器人技术方案.md#3.12.3
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class ArmPerceptionNode(Node):
    def __init__(self):
        super().__init__('hr_arm_perception')
        self.declare_parameter('hand_eye_calibration_file', '')
        if not str(self.get_parameter('hand_eye_calibration_file').value):
            raise RuntimeError(
                'hr_arm_perception refuses to start without a hand-eye calibration file; '
                'see docs/features/hr_arm.md §3')
        raise RuntimeError('hr_arm_perception is a skeleton: the wrist D435i is not fitted yet')


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ArmPerceptionNode()
    except RuntimeError:
        rclpy.shutdown()
        raise
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
