"""HMMD UART node. Disabled by default and never represents data as LaserScan."""
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from hr_interfaces.msg import HmmdDetection
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from .protocol import Parser, REPORT_MODE_COMMAND
from .serial_port import SerialPort


class HmmdNode(Node):
    def __init__(self):
        super().__init__('hr_hmmd')
        self.declare_parameter('transport_enabled', False)
        self.declare_parameter('port', '/dev/hmmd_radar')
        self.declare_parameter('baud', 115200)
        self.declare_parameter('range_scale_m', 0.0)
        self.declare_parameter('configure_report_mode', True)
        self.declare_parameter('stale_after_sec', 0.5)
        self.pub = self.create_publisher(HmmdDetection, '/hmmd/detection', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.parser = Parser(); self.serial = None; self.count = 0
        self.last_frame_monotonic = None
        if bool(self.get_parameter('transport_enabled').value):
            self.serial = SerialPort(str(self.get_parameter('port').value),
                                     int(self.get_parameter('baud').value))
            if bool(self.get_parameter('configure_report_mode').value):
                self.serial.write(REPORT_MODE_COMMAND)
                self.serial.flush()
                self.get_logger().info('requested HMMD binary report mode')
            self.create_timer(0.01, self.read)
        self.create_timer(1.0, self.publish_diagnostic)

    def read(self):
        for item in self.parser.feed(self.serial.read(self.serial.in_waiting or 1)):
            msg = HmmdDetection(); msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'hmmd_link'; msg.presence = item.presence
            scale = float(self.get_parameter('range_scale_m').value)
            msg.range_raw = item.range_raw
            msg.range_m = item.range_raw * scale if scale > 0 else float('nan')
            msg.energy_bins = list(item.energy); msg.valid = scale > 0; msg.mode = 'report'
            self.pub.publish(msg); self.count += 1
            self.last_frame_monotonic = time.monotonic()

    def publish_diagnostic(self):
        msg = DiagnosticArray(); msg.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus(); status.name = 'HomeRobot/HMMD'
        age = None if self.last_frame_monotonic is None else time.monotonic() - self.last_frame_monotonic
        stale_after = float(self.get_parameter('stale_after_sec').value)
        if not self.serial:
            status.level = DiagnosticStatus.WARN
            status.message = 'transport disabled'
        elif age is None:
            status.level = DiagnosticStatus.ERROR
            status.message = 'serial open; no report frame received'
        elif age > stale_after:
            status.level = DiagnosticStatus.ERROR
            status.message = 'report data stale'
        else:
            status.level = DiagnosticStatus.OK
            status.message = 'report mode receiving'
        status.values = [KeyValue(key='frames', value=str(self.count)),
                         KeyValue(key='bad_frames', value=str(self.parser.bad_frames)),
                         KeyValue(key='last_frame_age_sec', value='never' if age is None else f'{age:.3f}'),
                         KeyValue(key='range_scale_m', value=str(self.get_parameter('range_scale_m').value)),
                         KeyValue(key='laser_scan_capable', value='false')]
        msg.status = [status]; self.diag.publish(msg)

    def destroy_node(self):
        if self.serial: self.serial.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = HmmdNode()
    try: rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException): pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
