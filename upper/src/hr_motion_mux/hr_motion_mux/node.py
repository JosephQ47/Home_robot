"""Sole publisher of /cmd_vel_auto.

Nav2 publishes /cmd_vel_nav, OpenNav Docking publishes /cmd_vel_dock, and this
node decides which one — if either — is allowed through. Downstream the value
still passes Collision Monitor and the STM32 limits; this node adds no limiting
of its own.

# @spec 家庭服务机器人技术方案.md#2.2
"""
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
from hr_interfaces.msg import MotionPhase
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from .mux import Limits, MotionMux

PHASE_NAMES = {0: 'ZERO', 1: 'NAVIGATING', 2: 'FOLLOWING', 3: 'DOCKING'}


class MotionMuxNode(Node):
    def __init__(self):
        super().__init__('hr_motion_mux')
        self.declare_parameter('publish_rate_hz', 50.0)
        self.declare_parameter('source_timeout_ms', 200)
        self.declare_parameter('phase_timeout_ms', 1000)
        self.declare_parameter('zero_hold_ms', 300)
        rate = float(self.get_parameter('publish_rate_hz').value)
        if rate <= 0.0:
            raise RuntimeError('publish_rate_hz must be positive')
        self.mux = MotionMux(limits=Limits(
            source_timeout_sec=int(self.get_parameter('source_timeout_ms').value) / 1000.0,
            phase_timeout_sec=int(self.get_parameter('phase_timeout_ms').value) / 1000.0,
            zero_hold_sec=int(self.get_parameter('zero_hold_ms').value) / 1000.0))
        self.pub = self.create_publisher(Twist, '/cmd_vel_auto', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(Twist, '/cmd_vel_nav', self.on_nav, 10)
        self.create_subscription(Twist, '/cmd_vel_dock', self.on_dock, 10)
        self.create_subscription(MotionPhase, '/task/motion_phase', self.on_phase, 10)
        self.ignored_phases = 0
        self.last_reason = ''
        self.create_timer(1.0 / rate, self.tick)
        self.create_timer(1.0, self.publish_diagnostics)

    def on_nav(self, msg):
        self.mux.on_nav(msg.linear.x, msg.angular.z, time.monotonic())

    def on_dock(self, msg):
        self.mux.on_dock(msg.linear.x, msg.angular.z, time.monotonic())

    def on_phase(self, msg):
        if not self.mux.on_phase(msg.phase, msg.source_seq, time.monotonic(), msg.zero_required):
            self.ignored_phases += 1

    def tick(self):
        decision = self.mux.decide(time.monotonic())
        self.last_reason = decision.reason
        out = Twist()
        # MUX-6: a four-wheel differential base has no lateral speed. Everything
        # except vx/wz stays at the Twist default of zero, on every single tick.
        out.linear.x = decision.vx
        out.angular.z = decision.wz
        self.pub.publish(out)

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_motion_mux', hardware_id='rk3588')
        status.level = (DiagnosticStatus.OK if self.last_reason in ('forward', 'phase_zero')
                        else DiagnosticStatus.WARN)
        status.message = self.last_reason
        status.values = [
            KeyValue(key='phase', value=PHASE_NAMES.get(self.mux.phase, str(self.mux.phase))),
            KeyValue(key='source_seq', value=str(self.mux.phase_seq)),
            KeyValue(key='ignored_phase_msgs', value=str(self.ignored_phases)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    node = MotionMuxNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
