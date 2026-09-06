"""Interface-valid perception stub used when no model backend is selected."""
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from hr_interfaces.msg import PerceptionControl
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


class PerceptionStub(Node):
    def __init__(self):
        super().__init__('hr_perception')
        self.enabled = False
        self.pub = self.create_publisher(Detection2DArray, '/detections', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(PerceptionControl, '/task/perception_control', self.on_control, 10)
        self.create_subscription(Image, '/camera/image_raw', self.on_image, qos_profile_sensor_data)
        self.create_timer(1.0, self.on_diagnostic)

    def on_control(self, msg):
        self.enabled = msg.enabled

    def on_image(self, msg):
        if self.enabled:
            output = Detection2DArray(); output.header = msg.header; self.pub.publish(output)

    def on_diagnostic(self):
        msg = DiagnosticArray(); msg.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus(); status.name = 'HomeRobot/Perception'
        status.level = DiagnosticStatus.WARN
        status.message = 'stub backend; no detections' if self.enabled else 'disabled by task policy'
        msg.status = [status]; self.diag.publish(msg)


def main(args=None):
    rclpy.init(args=args); node = PerceptionStub()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
