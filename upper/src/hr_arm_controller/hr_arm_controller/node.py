"""Runs the grasp state machine against the real arm. Hardware not fitted yet.

The state machine and its interlocks in grasp_state_machine.py are complete and
tested; what is missing is inverse kinematics and a driver to talk to. Rather
than shipping a node that would move a nonexistent arm on placeholder maths,
this refuses to start until the calibration file that only a real arm can
produce is present.

# @spec 家庭服务机器人技术方案.md#3.12.5
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from .grasp_state_machine import GraspStateMachine


class ArmControllerNode(Node):
    def __init__(self):
        super().__init__('hr_arm_controller')
        self.declare_parameter('calibration_file', '')
        self.declare_parameter('accepted_object_classes', [''])
        self.machine = GraspStateMachine()
        if not str(self.get_parameter('calibration_file').value):
            # ARM-2: a grasp without a valid hand-eye calibration is refused, and
            # an absent calibration is just the strongest form of invalid.
            raise RuntimeError(
                'hr_arm_controller refuses to start without a hand-eye calibration file; '
                'see docs/features/hr_arm.md §3')
        raise RuntimeError('hr_arm_controller is a skeleton: inverse kinematics and '
                           'hr_arm_driver are not implemented yet')


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ArmControllerNode()
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
