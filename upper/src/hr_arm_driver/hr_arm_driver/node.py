"""Link to the independent servo controller. Skeleton: controller not selected.

This node dispatches trajectories and reads back joint state and faults. It
never bypasses the servo controller's own limit and over-current protection —
those stay in the controller, close to the hardware.

# @spec 家庭服务机器人技术方案.md#3.12.1
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class ArmDriverNode(Node):
    def __init__(self):
        super().__init__('hr_arm_driver')
        self.declare_parameter('serial_port', '')
        if not str(self.get_parameter('serial_port').value):
            raise RuntimeError('hr_arm_driver needs a serial_port; the servo controller '
                               'has not been selected yet')
        raise RuntimeError('hr_arm_driver is a skeleton: no servo controller is fitted')


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ArmDriverNode()
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
