"""A 2D chassis and laser simulator, so the stack can be driven without hardware.

It closes the only loop the mock system never did: /cmd_vel actually moves the
robot, odometry follows, and /scan is ray-cast against a floor plan. That is
enough to build a map with slam_toolbox and then run the real Nav2 stack
against it.

It deliberately imitates the chassis limits the STM32 enforces — speed caps,
acceleration ramp and command timeout — because a simulator that accepts
commands the real base would refuse teaches the navigation stack the wrong
thing. It is a simulator and says so in its diagnostics; it is not a claim
about measured hardware behaviour.

# @spec 家庭服务机器人技术方案.md#3.9
"""
import math
import random

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped, Twist
from hr_interfaces.msg import RobotStatus
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Imu, LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster
import yaml

from .floorplan import blocked, build, clearance, scan as cast_scan


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


class PlanarSim(Node):
    def __init__(self):
        super().__init__('hr_planar_sim')
        self.declare_parameter('floorplan_file', '')
        self.declare_parameter('rate_hz', 30.0)
        self.declare_parameter('scan_rate_hz', 10.0)
        # Chassis limits, mirrored from nav2_params.yaml so the simulator refuses
        # what the real base would refuse.
        self.declare_parameter('max_vel_x', 0.45)
        self.declare_parameter('max_vel_theta', 1.2)
        self.declare_parameter('accel_x', 1.0)
        self.declare_parameter('decel_x', 1.5)
        self.declare_parameter('accel_theta', 2.0)
        self.declare_parameter('command_timeout_ms', 150)
        # RPLIDAR S3.
        self.declare_parameter('scan_angle_increment_deg', 0.5)
        self.declare_parameter('scan_max_range', 25.0)
        self.declare_parameter('scan_min_range', 0.15)
        self.declare_parameter('scan_noise_m', 0.012)
        self.declare_parameter('laser_offset_x', 0.10)
        self.declare_parameter('laser_height', 0.28)
        self.declare_parameter('odom_noise', 0.004)
        self.declare_parameter('publish_map_tf', False)
        # Half the chassis width. A step that would put the body inside a wall
        # is refused rather than executed.
        self.declare_parameter('robot_radius', 0.25)

        path = str(self.get_parameter('floorplan_file').value)
        if not path:
            raise RuntimeError('hr_planar_sim needs floorplan_file')
        plan = yaml.safe_load(open(path, encoding='utf-8'))['floorplan']
        self.segments = build(plan)
        start = plan.get('start', {'x': 0.0, 'y': 0.0, 'yaw': 0.0})
        # True pose in the map frame, and the odometry estimate that drifts from it.
        self.x, self.y, self.yaw = start['x'], start['y'], start['yaw']
        self.ox, self.oy, self.oyaw = 0.0, 0.0, 0.0
        self.vx = self.wz = 0.0
        self.cmd_vx = self.cmd_wz = 0.0
        self.cmd_stamp = float('-inf')
        self.rng = random.Random(20260918)
        # Stamp shared by the pose TF and the scan. A scan stamped later than the
        # newest odom->base_link transform cannot be transformed yet, and
        # slam_toolbox's message filter drops it — which looks like a mapping
        # quality problem and is really a timestamp race.
        self.stamp = None
        self.collisions = 0

        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.odom_pub = self.create_publisher(Odometry, '/wheel/odom_raw', 20)
        self.filtered_pub = self.create_publisher(Odometry, '/odometry/filtered', 20)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 20)
        self.status_pub = self.create_publisher(RobotStatus, '/robot_status', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.tf = TransformBroadcaster(self)
        self.static_tf = StaticTransformBroadcaster(self)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 10)

        laser = TransformStamped()
        laser.header.stamp = self.get_clock().now().to_msg()
        laser.header.frame_id = 'base_link'
        laser.child_frame_id = 'laser_frame'
        laser.transform.translation.x = float(self.get_parameter('laser_offset_x').value)
        laser.transform.translation.z = float(self.get_parameter('laser_height').value)
        laser.transform.rotation.w = 1.0
        self.static_tf.sendTransform(laser)

        rate = float(self.get_parameter('rate_hz').value)
        self.dt = 1.0 / rate
        self.create_timer(self.dt, self.step)
        self.create_timer(1.0 / float(self.get_parameter('scan_rate_hz').value),
                          self.publish_scan)
        self.create_timer(1.0, self.publish_diagnostics)
        self.get_logger().warning(
            'hr_planar_sim is a SIMULATOR: /scan and odometry are computed from '
            f'{path}, not measured. {len(self.segments)} wall segments loaded.')

    def on_cmd(self, msg):
        self.cmd_vx, self.cmd_wz = msg.linear.x, msg.angular.z
        self.cmd_stamp = self.now()

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def ramp(self, current, target, accel, decel):
        """Move `current` toward `target`, faster when slowing than speeding up."""
        limit = (accel if abs(target) > abs(current) else decel) * self.dt
        delta = target - current
        return target if abs(delta) <= limit else current + math.copysign(limit, delta)

    def step(self):
        timeout = int(self.get_parameter('command_timeout_ms').value) / 1000.0
        if self.now() - self.cmd_stamp > timeout:
            # Same rule as the STM32: a command that stopped arriving means stop,
            # not carry on with the last one.
            target_vx = target_wz = 0.0
        else:
            target_vx = max(-float(self.get_parameter('max_vel_x').value),
                            min(float(self.get_parameter('max_vel_x').value), self.cmd_vx))
            target_wz = max(-float(self.get_parameter('max_vel_theta').value),
                            min(float(self.get_parameter('max_vel_theta').value), self.cmd_wz))

        self.vx = self.ramp(self.vx, target_vx,
                            float(self.get_parameter('accel_x').value),
                            float(self.get_parameter('decel_x').value))
        self.wz = self.ramp(self.wz, target_wz,
                            float(self.get_parameter('accel_theta').value),
                            float(self.get_parameter('accel_theta').value))

        radius = float(self.get_parameter('robot_radius').value)
        nx = self.x + self.vx * math.cos(self.yaw) * self.dt
        ny = self.y + self.vx * math.sin(self.yaw) * self.dt
        if blocked(nx, ny, self.segments, radius):
            # Refuse the translation and kill the forward speed. Rotation is still
            # allowed so the robot can turn away instead of being stuck forever.
            self.collisions += 1
            self.vx = 0.0
            if self.collisions % 30 == 1:
                self.get_logger().warning(
                    f'blocked at ({self.x:.2f}, {self.y:.2f}): '
                    f'wall {clearance(self.x, self.y, self.segments):.2f} m away')
        else:
            self.x, self.y = nx, ny
        self.yaw = wrap(self.yaw + self.wz * self.dt)

        # Odometry drifts: a perfect estimate would hide every localisation bug.
        noise = float(self.get_parameter('odom_noise').value)
        ovx = self.vx * (1.0 + self.rng.gauss(0.0, noise))
        owz = self.wz * (1.0 + self.rng.gauss(0.0, noise))
        self.ox += ovx * math.cos(self.oyaw) * self.dt
        self.oy += ovx * math.sin(self.oyaw) * self.dt
        self.oyaw = wrap(self.oyaw + owz * self.dt)

        now = self.get_clock().now().to_msg()
        self.stamp = now
        self.send_tf(now, 'odom', 'base_link', self.ox, self.oy, self.oyaw)
        if bool(self.get_parameter('publish_map_tf').value):
            # Only for bench runs with no SLAM or AMCL: they own map->odom.
            self.send_tf(now, 'map', 'odom', 0.0, 0.0, 0.0)

        odom = Odometry()
        odom.header.stamp, odom.header.frame_id = now, 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x, odom.pose.pose.position.y = self.ox, self.oy
        odom.pose.pose.orientation.z = math.sin(self.oyaw / 2)
        odom.pose.pose.orientation.w = math.cos(self.oyaw / 2)
        odom.twist.twist.linear.x, odom.twist.twist.angular.z = ovx, owz
        self.odom_pub.publish(odom)
        self.filtered_pub.publish(odom)

        imu = Imu()
        imu.header.stamp, imu.header.frame_id = now, 'imu_link'
        imu.orientation.z = math.sin(self.oyaw / 2)
        imu.orientation.w = math.cos(self.oyaw / 2)
        imu.angular_velocity.z = owz
        self.imu_pub.publish(imu)

        status = RobotStatus()
        status.header.stamp = now
        status.control_source = RobotStatus.CONTROL_AUTO
        status.stm32_link_ok = status.command_fresh = True
        status.wheel_odom_valid = status.imu_valid = True
        status.safety_permit = status.watchdog_healthy = True
        status.battery_voltage, status.battery_percent = 12.6, 82.0
        self.status_pub.publish(status)

    def send_tf(self, stamp, parent, child, x, y, yaw):
        t = TransformStamped()
        t.header.stamp, t.header.frame_id, t.child_frame_id = stamp, parent, child
        t.transform.translation.x, t.transform.translation.y = x, y
        t.transform.rotation.z = math.sin(yaw / 2)
        t.transform.rotation.w = math.cos(yaw / 2)
        self.tf.sendTransform(t)

    def publish_scan(self):
        if self.stamp is None:
            return          # no pose transform has been published yet
        inc = math.radians(float(self.get_parameter('scan_angle_increment_deg').value))
        max_range = float(self.get_parameter('scan_max_range').value)
        min_range = float(self.get_parameter('scan_min_range').value)
        offset = float(self.get_parameter('laser_offset_x').value)
        lx = self.x + offset * math.cos(self.yaw)
        ly = self.y + offset * math.sin(self.yaw)
        ranges = cast_scan((lx, ly, self.yaw), self.segments, -math.pi, math.pi,
                           inc, max_range)
        noise = float(self.get_parameter('scan_noise_m').value)
        out = []
        for r in ranges:
            if r >= max_range:
                out.append(float('inf'))          # out of range, as a real unit reports
                continue
            r += self.rng.gauss(0.0, noise)
            out.append(r if r > min_range else float('inf'))

        msg = LaserScan()
        # Reuse the last pose stamp rather than "now": the transform for this
        # instant is already published, so the scan can be transformed the moment
        # it arrives instead of queueing until it is dropped.
        msg.header.stamp = self.stamp
        msg.header.frame_id = 'laser_frame'
        msg.angle_min, msg.angle_max, msg.angle_increment = -math.pi, math.pi, inc
        msg.range_min, msg.range_max = min_range, max_range
        msg.scan_time = 1.0 / float(self.get_parameter('scan_rate_hz').value)
        msg.time_increment = msg.scan_time / max(1, len(out))
        msg.ranges = out
        self.scan_pub.publish(msg)

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_planar_sim', hardware_id='simulation')
        status.level = DiagnosticStatus.WARN     # never let this be mistaken for hardware
        status.message = 'simulated chassis and laser; no hardware attached'
        status.values = [
            KeyValue(key='wall_segments', value=str(len(self.segments))),
            KeyValue(key='true_pose',
                     value=f'{self.x:.2f}, {self.y:.2f}, {math.degrees(self.yaw):.0f}deg'),
            KeyValue(key='vx', value=f'{self.vx:.3f}'),
            KeyValue(key='collisions', value=str(self.collisions)),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)


def main(args=None):
    rclpy.init(args=args)
    try:
        node = PlanarSim()
    except (RuntimeError, OSError) as exc:
        print(f'hr_planar_sim: {exc}')
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
