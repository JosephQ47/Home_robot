"""ROS 2 node joining /cmd_vel and the STM32 USB-UART controller."""

from __future__ import annotations

import math
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
from hr_interfaces.msg import RobotStatus
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu

from .protocol import ID_STATE, Parser, decode_state, velocity_frame
from .serial_port import SerialPort


class SerialTransport:
    def __init__(self, port: str, baudrate: int) -> None:
        self.serial = SerialPort(port, baudrate)

    def write(self, data: bytes) -> None:
        self.serial.write(data)

    def read(self) -> bytes:
        return self.serial.read(self.serial.in_waiting or 1)

    def close(self) -> None:
        self.serial.close()


class DisabledTransport:
    def write(self, _data: bytes) -> None:
        return

    def read(self) -> bytes:
        return b""

    def close(self) -> None:
        return


class Stm32Bridge(Node):
    def __init__(self) -> None:
        super().__init__("hr_bridge")
        self.declare_parameter("port", "/dev/robot_mcu")
        self.declare_parameter("baud", 230400)
        self.declare_parameter("transport_enabled", False)
        self.declare_parameter("command_output_enabled", False)
        self.declare_parameter("command_hz", 50.0)
        self.declare_parameter("read_hz", 100.0)
        self.declare_parameter("command_timeout", 0.25)
        self.declare_parameter("max_linear_mps", 0.10)
        self.declare_parameter("max_angular_rps", 0.30)
        self.declare_parameter("legacy_firmware_watchdog_verified", False)
        self.declare_parameter("bench_motion_authorized", False)
        self.declare_parameter("accel_scale", 0.0)
        self.declare_parameter("gyro_scale", 0.0)
        port = str(self.get_parameter("port").value)
        baud = int(self.get_parameter("baud").value)
        self.command_timeout = float(self.get_parameter("command_timeout").value)
        self.accel_scale = float(self.get_parameter("accel_scale").value)
        self.gyro_scale = float(self.get_parameter("gyro_scale").value)
        self.transport_enabled = bool(self.get_parameter("transport_enabled").value)
        self.command_output_enabled = bool(self.get_parameter("command_output_enabled").value)
        self.firmware_watchdog_verified = bool(
            self.get_parameter("legacy_firmware_watchdog_verified").value)
        self.bench_motion_authorized = bool(self.get_parameter("bench_motion_authorized").value)
        if self.command_output_enabled and not self.transport_enabled:
            raise ValueError("command_output_enabled requires transport_enabled")
        if self.command_output_enabled and not self.firmware_watchdog_verified:
            raise ValueError("legacy command output requires a verified firmware watchdog")
        if self.command_output_enabled and not self.bench_motion_authorized:
            raise ValueError("legacy command output requires explicit bench_motion_authorized=true")
        if float(self.get_parameter("max_linear_mps").value) <= 0.0:
            raise ValueError("max_linear_mps must be positive")
        if float(self.get_parameter("max_angular_rps").value) <= 0.0:
            raise ValueError("max_angular_rps must be positive")
        self.transport = SerialTransport(port, baud) if self.transport_enabled else DisabledTransport()
        self.parser = Parser()
        self.last_cmd = Twist()
        self.last_cmd_time = 0.0
        self.last_state_time = 0.0
        self.last_battery_voltage = 0.0

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.cmd_sub = self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        self.odom_pub = self.create_publisher(Odometry, "/wheel/odom_raw", qos)
        self.imu_pub = self.create_publisher(Imu, "/imu/data", qos)
        self.status_pub = self.create_publisher(RobotStatus, "/robot_status", 10)
        self.diag_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        command_period = 1.0 / float(self.get_parameter("command_hz").value)
        read_period = 1.0 / float(self.get_parameter("read_hz").value)
        self.command_timer = self.create_timer(command_period, self.send_command)
        self.read_timer = self.create_timer(read_period, self.read_serial)
        self.status_timer = self.create_timer(1.0, self.publish_link_status)
        mode = f"opening {port} @ {baud}" if self.transport_enabled else "transport disabled (safe mode)"
        self.get_logger().info(f"hr_bridge {mode}")

    def on_cmd_vel(self, msg: Twist) -> None:
        self.last_cmd = msg
        self.last_cmd_time = time.monotonic()

    def send_command(self) -> None:
        if not self.command_output_enabled:
            return
        msg = self.last_cmd if time.monotonic() - self.last_cmd_time <= self.command_timeout else Twist()
        try:
            # The selected chassis is four-wheel differential: lateral
            # velocity is not supported even though the legacy frame reserves
            # a Y field.
            self.transport.write(
                velocity_frame(*self.bounded_velocity(msg))
            )
        except (OSError, ValueError) as exc:
            self.get_logger().error(f"STM32 command write failed: {exc}")

    def bounded_velocity(self, msg: Twist) -> tuple[int, int, int]:
        linear = float(msg.linear.x)
        angular = float(msg.angular.z)
        if not math.isfinite(linear) or not math.isfinite(angular):
            return 0, 0, 0
        linear_limit = float(self.get_parameter("max_linear_mps").value)
        angular_limit = float(self.get_parameter("max_angular_rps").value)
        linear = max(-linear_limit, min(linear_limit, linear))
        angular = max(-angular_limit, min(angular_limit, angular))
        return round(linear * 1000), 0, round(angular * 1000)

    def read_serial(self) -> None:
        if not self.transport_enabled:
            return
        try:
            data = self.transport.read()
        except OSError as exc:
            self.get_logger().error(f"STM32 serial read failed: {exc}")
            return
        for frame in self.parser.feed(data):
            if frame[3] != ID_STATE:
                continue
            try:
                self.publish_state(decode_state(frame))
            except ValueError as exc:
                self.get_logger().warning(f"invalid STM32 state frame: {exc}")

    def publish_state(self, state) -> None:
        now = self.get_clock().now().to_msg()
        self.last_state_time = time.monotonic()
        self.last_battery_voltage = state.battery_x100 / 100.0
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.twist.twist.linear.x = state.velocity[0] / 1000.0
        odom.twist.twist.linear.y = state.velocity[1] / 1000.0
        odom.twist.twist.angular.z = state.velocity[2] / 1000.0
        self.odom_pub.publish(odom)

        imu = Imu()
        imu.header.stamp = now
        imu.header.frame_id = "imu_link"
        # The PDF protocol carries accel/gyro only; do not advertise a fake
        # orientation to robot_localization.
        imu.orientation_covariance[0] = -1.0
        if self.accel_scale > 0 and self.gyro_scale > 0:
            imu.linear_acceleration.x = state.accel[0] * self.accel_scale
            imu.linear_acceleration.y = state.accel[1] * self.accel_scale
            imu.linear_acceleration.z = state.accel[2] * self.accel_scale
            imu.angular_velocity.x = state.gyro[0] * self.gyro_scale
            imu.angular_velocity.y = state.gyro[1] * self.gyro_scale
            imu.angular_velocity.z = state.gyro[2] * self.gyro_scale
        else:
            imu.linear_acceleration_covariance[0] = -1.0
            imu.angular_velocity_covariance[0] = -1.0
        self.imu_pub.publish(imu)

        status = DiagnosticStatus()
        status.name = "STM32F407"
        status.level = DiagnosticStatus.OK
        status.message = "state frame received"
        status.values = [
            KeyValue(key="battery_voltage", value=f"{state.battery_x100 / 100:.2f} V"),
            KeyValue(key="velocity_mm_s", value=str(state.velocity)),
            KeyValue(key="protocol_bad_frames", value=str(self.parser.bad_frames)),
        ]
        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = now
        diagnostics.status = [status]
        self.diag_pub.publish(diagnostics)
        self.publish_link_status()

    def publish_link_status(self) -> None:
        msg = RobotStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        fresh = self.transport_enabled and time.monotonic() - self.last_state_time < 0.5
        msg.stm32_link_ok = fresh
        # These two explicit gates are only for a wheel-off-ground legacy bench test.
        # The production V1 protocol must report these states from the MCU itself.
        legacy_bench_safe = (fresh and self.command_output_enabled and
                             self.firmware_watchdog_verified and self.bench_motion_authorized)
        msg.control_source = RobotStatus.CONTROL_AUTO if legacy_bench_safe else RobotStatus.CONTROL_UNKNOWN
        msg.command_fresh = legacy_bench_safe
        msg.wheel_odom_valid = fresh
        msg.imu_valid = fresh and self.accel_scale > 0 and self.gyro_scale > 0
        msg.safety_permit = legacy_bench_safe
        msg.watchdog_healthy = legacy_bench_safe
        msg.battery_voltage = self.last_battery_voltage
        msg.fault_message = ("" if legacy_bench_safe else
                             "legacy protocol awaiting freeze" if fresh else
                             "STM32 transport disabled or stale")
        self.status_pub.publish(msg)

    def destroy_node(self):
        try:
            if self.command_output_enabled:
                self.transport.write(velocity_frame(0, 0, 0))
            self.transport.close()
        except OSError:
            pass
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = Stm32Bridge()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (RuntimeError, OSError) as exc:
        if node:
            node.get_logger().error(str(exc))
        else:
            print(f"hr_bridge failed: {exc}")
    finally:
        if node:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
