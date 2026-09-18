"""Drive the simulated robot through every room so slam_toolbox sees them all.

A simple pose controller on /cmd_vel: turn toward the next waypoint, drive to
it, then turn to the next. It publishes to /cmd_vel directly because this is a
mapping run — the arbitration and veto chain is exercised separately.
"""
import math
import sys
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node

# Through the doorways, covering all five rooms and returning to the start.
TOUR = [
    (2.00, 5.20), (1.85, 5.35), (1.70, 5.50), (1.55, 5.65), (1.40, 5.80),
    (1.25, 5.95), (1.20, 6.00), (1.35, 6.00), (1.55, 6.00), (1.70, 6.05),
    (1.85, 6.05), (2.05, 6.05), (2.20, 6.20), (2.35, 6.35), (2.50, 6.40),
    (2.65, 6.45), (2.80, 6.55), (2.90, 6.60), (2.75, 6.45), (2.60, 6.30),
    (2.45, 6.15), (2.30, 6.00), (2.15, 5.85), (2.00, 5.70), (1.95, 5.55),
    (1.90, 5.40), (1.75, 5.25), (1.60, 5.10), (1.45, 4.95), (1.30, 4.80),
    (1.15, 4.65), (1.05, 4.50), (1.00, 4.40), (1.15, 4.25), (1.30, 4.10),
    (1.45, 3.95), (1.60, 3.80), (1.75, 3.65), (1.80, 3.60), (1.70, 3.45),
    (1.65, 3.30), (1.60, 3.10), (1.45, 2.95), (1.30, 2.80), (1.15, 2.65),
    (1.00, 2.60), (1.15, 2.60), (1.30, 2.60), (1.45, 2.50), (1.60, 2.50),
    (1.80, 2.45), (1.95, 2.45), (2.10, 2.45), (2.30, 2.45), (2.45, 2.45),
    (2.60, 2.40), (2.40, 2.40), (2.25, 2.35), (2.10, 2.30), (1.90, 2.30),
    (1.75, 2.25), (1.55, 2.25), (1.35, 2.25), (1.20, 2.20), (1.25, 2.35),
    (1.35, 2.50), (1.35, 2.65), (1.45, 2.80), (1.50, 2.95), (1.60, 3.10),
    (1.65, 3.25), (1.70, 3.40), (1.75, 3.55), (1.80, 3.60), (1.80, 3.40),
    (1.85, 3.25), (1.90, 3.10), (1.90, 2.90), (1.95, 2.75), (1.95, 2.55),
    (2.00, 2.35), (2.05, 2.20), (2.15, 2.05), (2.30, 1.90), (2.45, 1.75),
    (2.45, 1.55), (2.45, 1.35), (2.50, 1.20), (2.55, 1.05), (2.60, 1.00),
    (2.75, 1.15), (2.90, 1.30), (3.05, 1.45), (3.20, 1.45), (3.40, 1.40),
    (3.55, 1.25), (3.70, 1.10), (3.85, 1.00), (4.00, 0.90), (4.15, 1.05),
    (4.25, 1.20), (4.35, 1.35), (4.50, 1.50), (4.65, 1.65), (4.80, 1.70),
    (4.95, 1.70), (5.10, 1.70), (5.25, 1.70), (5.40, 1.85), (5.55, 2.00),
    (5.70, 2.15), (5.80, 2.20), (5.60, 2.20), (5.45, 2.25), (5.30, 2.30),
    (5.10, 2.30), (4.95, 2.35), (4.75, 2.35), (4.55, 2.35), (4.35, 2.35),
    (4.20, 2.45), (4.05, 2.55), (4.00, 2.60), (4.15, 2.60), (4.30, 2.75),
    (4.45, 2.75), (4.60, 2.75), (4.75, 2.80), (4.90, 2.85), (5.05, 2.95),
    (5.20, 3.00), (5.20, 3.15), (5.20, 3.30), (5.20, 3.45), (5.20, 3.65),
    (5.20, 3.80), (5.20, 3.95), (5.20, 4.10), (5.20, 4.25), (5.20, 4.40),
    (5.35, 4.40), (5.50, 4.40), (5.65, 4.50), (5.80, 4.50), (5.95, 4.55),
    (6.10, 4.60), (5.90, 4.60), (5.75, 4.60), (5.55, 4.60), (5.35, 4.60),
    (5.15, 4.60), (5.00, 4.60), (4.80, 4.60), (4.60, 4.60), (4.40, 4.60),
    (4.55, 4.75), (4.70, 4.90), (4.85, 5.05), (5.00, 5.20), (5.10, 5.35),
    (5.15, 5.50), (5.20, 5.60), (5.05, 5.70), (4.90, 5.75), (4.75, 5.85),
    (4.60, 5.90), (4.45, 5.95), (4.40, 6.00), (4.60, 6.00), (4.75, 6.05),
    (4.90, 6.10), (5.05, 6.10), (5.20, 6.15), (5.35, 6.15), (5.50, 6.15),
    (5.65, 6.15), (5.80, 6.15), (5.95, 6.15), (6.00, 6.20), (5.85, 6.05),
    (5.70, 5.90), (5.55, 5.75), (5.40, 5.70), (5.25, 5.60), (5.20, 5.60),
    (5.15, 5.45), (5.15, 5.25), (5.15, 5.05), (5.15, 4.85), (5.15, 4.65),
    (5.15, 4.50), (5.15, 4.30), (5.15, 4.10), (5.15, 3.90), (5.15, 3.70),
    (5.20, 3.60), (5.20, 3.40), (5.20, 3.20), (5.20, 3.00), (5.20, 2.80),
    (5.20, 2.60), (5.20, 2.40), (5.20, 2.20), (5.20, 2.00), (5.00, 1.95),
    (4.85, 1.85), (4.65, 1.85), (4.50, 1.80), (4.35, 1.75), (4.20, 1.65),
    (4.05, 1.60), (3.90, 1.55), (3.75, 1.45), (3.60, 1.40), (3.45, 1.55),
    (3.30, 1.70), (3.15, 1.75), (3.00, 1.80), (2.85, 1.95), (2.70, 2.10),
    (2.55, 2.25), (2.40, 2.30), (2.25, 2.40), (2.10, 2.55), (1.95, 2.70),
    (1.80, 2.80), (1.80, 2.95), (1.80, 3.15), (1.80, 3.30), (1.80, 3.45),
    (1.80, 3.60), (1.80, 3.80), (1.85, 3.95), (1.90, 4.10), (1.90, 4.25),
    (1.95, 4.40), (1.95, 4.60), (1.95, 4.75), (1.95, 4.90), (1.95, 5.05),
    (2.00, 5.20),
]


class Tour(Node):
    def __init__(self):
        super().__init__('drive_tour')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pose = None
        self.create_subscription(Odometry, '/odometry/filtered', self.on_odom, 20)
        self.i = 0
        self.stuck = 0
        self.last_xy = (0.0, 0.0)
        self.start = time.time()
        self.create_timer(0.05, self.tick)
        self.done = False

    def on_odom(self, msg):
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z), 1 - 2 * q.z * q.z)
        self.pose = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def tick(self):
        if self.pose is None or self.done:
            return
        # The tour is written in map coordinates; odometry starts at zero at the
        # floor plan's start pose, so shift the targets into the odom frame.
        ox, oy = TOUR[0]
        tx, ty = TOUR[self.i]
        gx, gy = tx - ox, ty - oy
        x, y, yaw = self.pose
        dx, dy = gx - x, gy - y
        dist = math.hypot(dx, dy)
        if dist < 0.09:
            self.i += 1
            self.stuck = 0
            if self.i >= len(TOUR):
                self.pub.publish(Twist())
                self.done = True
                self.get_logger().info(f'tour complete in {time.time() - self.start:.0f}s')
            return
        err = math.atan2(math.sin(math.atan2(dy, dx) - yaw),
                         math.cos(math.atan2(dy, dx) - yaw))

        # Stall recovery, judged by actual displacement rather than by distance
        # to the goal. Distance to the goal does not shrink while the robot turns
        # in place — a 90 degree turn at 0.45 rad/s takes 3.5 s — so a
        # distance-based detector fires on every large turn and sends the robot
        # reversing and spinning for no reason. That churn is what loses SLAM.
        moved = math.hypot(x - self.last_xy[0], y - self.last_xy[1])
        self.last_xy = (x, y)
        turning = abs(err) > 0.35
        if turning or moved > 0.002:
            self.stuck = 0
        else:
            self.stuck += 1

        cmd = Twist()
        if self.stuck > 40:
            cmd.linear.x = -0.10
            cmd.angular.z = 0.6
            self.pub.publish(cmd)
            if self.stuck > 90:
                self.get_logger().warning(f'giving up on waypoint {self.i}')
                self.i += 1
                self.stuck = 0
            return

        if abs(err) > 0.35:
            cmd.angular.z = max(-0.45, min(0.45, 1.2 * err))     # turn in place first
        else:
            cmd.linear.x = max(0.06, min(0.22, 0.7 * dist))
            cmd.angular.z = max(-0.35, min(0.35, 1.0 * err))
        self.pub.publish(cmd)


rclpy.init()
node = Tour()
deadline = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 240)
while rclpy.ok() and time.time() < deadline and not node.done:
    rclpy.spin_once(node, timeout_sec=0.05)
node.pub.publish(Twist())
time.sleep(0.5)
print('waypoints reached:', node.i, 'of', len(TOUR))
node.destroy_node()
rclpy.shutdown()
