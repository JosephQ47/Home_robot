"""Compare what SLAM thinks the robot's pose is against the simulator's truth.

If the two agree on a simple motion, the mapping problem is in the tour; if they
diverge immediately, it is in the scan or the odometry the simulator produces.
"""
import math
import re
import subprocess
import threading
import time

from geometry_msgs.msg import Twist
from diagnostic_msgs.msg import DiagnosticArray
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener


class Track(Node):
    def __init__(self):
        super().__init__('slam_track')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.truth = None
        self.create_subscription(DiagnosticArray, '/diagnostics', self.on_diag, 20)

    def on_diag(self, msg):
        for st in msg.status:
            if st.name != 'hr_planar_sim':
                continue
            for kv in st.values:
                if kv.key == 'true_pose':
                    m = re.match(r'\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)deg', kv.value)
                    if m:
                        self.truth = (float(m.group(1)), float(m.group(2)),
                                      math.radians(float(m.group(3))))

    def slam_pose(self):
        try:
            t = self.buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
        except Exception:
            return None
        q = t.transform.rotation
        return (t.transform.translation.x, t.transform.translation.y,
                math.atan2(2 * (q.w * q.z), 1 - 2 * q.z * q.z))

    def drive(self, vx, wz, seconds):
        end = time.time() + seconds
        while time.time() < end:
            c = Twist(); c.linear.x = vx; c.angular.z = wz
            self.pub.publish(c)
            time.sleep(0.05)
        self.pub.publish(Twist())
        time.sleep(1.0)


def report(node, label):
    s, t = node.slam_pose(), node.truth
    if s is None or t is None:
        print(f'  {label:14} slam={s} truth={t}')
        return
    # SLAM's map frame is anchored at the robot's start, so compare the motion
    # from the start rather than absolute coordinates.
    print(f'  {label:14} slam=({s[0]:+.3f}, {s[1]:+.3f}, {math.degrees(s[2]):+6.1f}deg)  '
          f'truth=({t[0]:+.3f}, {t[1]:+.3f}, {math.degrees(t[2]):+6.1f}deg)')
    return s, t


rclpy.init()
n = Track()
ex = MultiThreadedExecutor(); ex.add_node(n)
threading.Thread(target=ex.spin, daemon=True).start()
time.sleep(4.0)

print('=== start ===')
s0 = report(n, 'initial')
print('=== drive straight 0.20 m/s for 6 s (~1.2 m) ===')
n.drive(0.20, 0.0, 6.0)
s1 = report(n, 'after line')
print('=== turn in place 0.30 rad/s for 5 s (~86 deg) ===')
n.drive(0.0, 0.30, 5.0)
s2 = report(n, 'after turn')
print('=== drive straight again 6 s ===')
n.drive(0.20, 0.0, 6.0)
s3 = report(n, 'after line 2')

if s0 and s3:
    (sx0, sy0, _), (tx0, ty0, _) = s0
    (sx3, sy3, _), (tx3, ty3, _) = s3
    ds = math.hypot(sx3 - sx0, sy3 - sy0)
    dt = math.hypot(tx3 - tx0, ty3 - ty0)
    print(f'\n  displacement  slam={ds:.3f} m  truth={dt:.3f} m  error={abs(ds-dt):.3f} m')

rclpy.shutdown()
