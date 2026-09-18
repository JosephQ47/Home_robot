"""Dispatches joint trajectories to the independent servo controller.

It forwards and reports; it does not decide. Joint limits, over-current cutoff
and action timeout live in the controller, where a hung RK3588 cannot switch
them off (技术方案 §3.12.1).

# @spec 家庭服务机器人技术方案.md#3.12.1
"""
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from trajectory_msgs.msg import JointTrajectory

from .protocol import Decoder, encode_gripper, encode_joints, encode_stop
from .transport import MockController, make_transport

JOINT_NAMES = [f'joint_{i}' for i in range(1, 7)]


class ArmDriverNode(Node):
    def __init__(self):
        super().__init__('hr_arm_driver')
        self.declare_parameter('transport', 'mock')
        self.declare_parameter('serial_port', '')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('status_rate_hz', 50.0)
        self.declare_parameter('status_timeout_ms', 500)
        self.declare_parameter('default_move_duration_ms', 800)

        kind = str(self.get_parameter('transport').value)
        port = str(self.get_parameter('serial_port').value)
        if kind == 'serial' and not port:
            raise RuntimeError('transport=serial needs serial_port; the servo '
                               'controller has not been selected yet')
        self.transport = make_transport(kind, port,
                                        int(self.get_parameter('baudrate').value),
                                        self.get_logger())
        self.decoder = Decoder()
        self.status = None
        self.status_stamp = float('-inf')
        self.write_failures = 0

        self.joint_pub = self.create_publisher(JointState, '/arm/joint_states', 10)
        self.fault_pub = self.create_publisher(String, '/arm/faults', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(JointTrajectory, '/arm/joint_trajectory',
                                 self.on_trajectory, 10)
        self.create_subscription(Float32, '/arm/gripper_command', self.on_gripper, 10)
        self.create_subscription(Bool, '/arm/stop', self.on_stop, 10)

        rate = float(self.get_parameter('status_rate_hz').value)
        if rate <= 0.0:
            raise RuntimeError('status_rate_hz must be positive')
        self.create_timer(1.0 / rate, self.poll)
        self.create_timer(1.0, self.publish_diagnostics)

    def send(self, frame):
        if not self.transport.write(frame):
            self.write_failures += 1

    def on_trajectory(self, msg):
        """Send only the final point: the controller does its own interpolation."""
        if not msg.points:
            return
        point = msg.points[-1]
        if len(point.positions) != 6:
            self.get_logger().warning(
                f'ignoring trajectory with {len(point.positions)} joints, expected 6')
            return
        duration_ms = int(point.time_from_start.sec * 1000 +
                          point.time_from_start.nanosec / 1e6)
        if duration_ms <= 0:
            duration_ms = int(self.get_parameter('default_move_duration_ms').value)
        self.send(encode_joints(point.positions, duration_ms))

    def on_gripper(self, msg):
        self.send(encode_gripper(float(msg.data),
                                 int(self.get_parameter('default_move_duration_ms').value)))

    def on_stop(self, msg):
        # ARM-4: stop is unconditional and is never rate limited.
        if msg.data:
            self.send(encode_stop())

    def poll(self):
        for status in self.decoder.feed(self.transport.read()):
            self.status, self.status_stamp = status, time.monotonic()
            state = JointState()
            state.header.stamp = self.get_clock().now().to_msg()
            state.name = JOINT_NAMES + ['gripper']
            state.position = list(status.positions) + [status.gripper_width]
            state.effort = list(status.currents) + [0.0]
            self.joint_pub.publish(state)
            if status.faults:
                self.fault_pub.publish(String(data=','.join(status.faults)))

    def stale(self):
        timeout = int(self.get_parameter('status_timeout_ms').value) / 1000.0
        return time.monotonic() - self.status_stamp > timeout

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_arm_driver', hardware_id='servo_controller')
        if self.status is None or self.stale():
            status.level, status.message = DiagnosticStatus.ERROR, 'no_status'
        elif self.status.faults:
            status.level, status.message = DiagnosticStatus.ERROR, ','.join(self.status.faults)
        else:
            status.level, status.message = DiagnosticStatus.OK, 'ok'
        status.values = [
            KeyValue(key='transport',
                     value='mock' if isinstance(self.transport, MockController) else 'serial'),
            KeyValue(key='crc_errors', value=str(self.decoder.crc_errors)),
            KeyValue(key='dropped_bytes', value=str(self.decoder.dropped_bytes)),
            KeyValue(key='write_failures', value=str(self.write_failures)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)

    def destroy_node(self):
        try:
            self.transport.close()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ArmDriverNode()
    except (RuntimeError, ValueError) as exc:
        print(f'hr_arm_driver: {exc}')
        rclpy.shutdown()
        raise SystemExit(1)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
