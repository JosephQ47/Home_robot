"""ROS-side state cache for the web API. It has no velocity interface."""
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from hr_interfaces.action import ExecuteTask
from hr_interfaces.msg import FollowTarget, RobotStatus, TaskStatus
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node


class WebRosAdapter(Node):
    def __init__(self):
        super().__init__('hr_web_ui')
        self.task_status = None; self.robot_status = None; self.follow_target = None
        self.client = ActionClient(self, ExecuteTask, '/task/execute')
        self.create_subscription(TaskStatus, '/task/status', lambda msg: setattr(self, 'task_status', msg), 10)
        self.create_subscription(RobotStatus, '/robot_status', lambda msg: setattr(self, 'robot_status', msg), 10)
        self.create_subscription(FollowTarget, '/follow_target', lambda msg: setattr(self, 'follow_target', msg), 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_timer(1.0, self.publish_diagnostic)

    def publish_diagnostic(self):
        msg = DiagnosticArray(); msg.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus(); status.name = 'HomeRobot/WebRosAdapter'
        status.level = DiagnosticStatus.OK if self.client.server_is_ready() else DiagnosticStatus.WARN
        status.message = 'task action ready' if self.client.server_is_ready() else 'waiting for /task/execute'
        msg.status = [status]; self.diag.publish(msg)


def main(args=None):
    rclpy.init(args=args); node = WebRosAdapter()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
