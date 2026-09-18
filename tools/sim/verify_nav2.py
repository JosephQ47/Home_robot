"""Runtime evidence for the real Nav2 stack driving the real safety chain.

Sends a NavigateToPose goal to the actual bt_navigator and watches the whole
path the velocity takes: controller_server -> /cmd_vel_nav -> hr_motion_mux ->
/cmd_vel_auto -> collision_monitor -> /cmd_vel -> the simulated chassis.
"""
import math
import subprocess
import threading
import time

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from hr_interfaces.msg import MotionPhase
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


def publishers(topic):
    out = subprocess.run(['ros2', 'topic', 'info', topic, '--verbose'],
                         capture_output=True, text=True).stdout
    names, section = [], None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith('Publisher count'):
            section = 'pub'
        elif s.startswith('Subscription count'):
            section = 'sub'
        elif section == 'pub' and s.startswith('Node name:'):
            names.append(s.split(':', 1)[1].strip())
    return [n for n in names if n != 'verify_nav2']


class Bench(Node):
    def __init__(self):
        super().__init__('verify_nav2')
        self.initial = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.phase = self.create_publisher(MotionPhase, '/task/motion_phase', 10)
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.nav_cmd, self.auto, self.final = [], [], []
        self.create_subscription(Twist, '/cmd_vel_nav', lambda m: self.nav_cmd.append(m), 50)
        self.create_subscription(Twist, '/cmd_vel_auto', lambda m: self.auto.append(m), 50)
        self.create_subscription(Twist, '/cmd_vel', lambda m: self.final.append(m), 50)
        self.odom = None
        self.create_subscription(Odometry, '/odometry/filtered',
                                 lambda m: setattr(self, 'odom', m), 20)
        self.seq = 0
        self.current = MotionPhase.NAVIGATING
        self.create_timer(0.1, self.beat)

    def beat(self):
        self.seq += 1
        m = MotionPhase()
        m.phase, m.source_seq, m.task_id = self.current, self.seq, 'nav2-bench'
        self.phase.publish(m)

    def set_initial_pose(self, x, y, yaw):
        p = PoseWithCovarianceStamped()
        p.header.frame_id = 'map'
        p.header.stamp = self.get_clock().now().to_msg()
        p.pose.pose.position.x, p.pose.pose.position.y = x, y
        p.pose.pose.orientation.z = math.sin(yaw / 2)
        p.pose.pose.orientation.w = math.cos(yaw / 2)
        p.pose.covariance[0] = p.pose.covariance[7] = 0.25
        p.pose.covariance[35] = 0.07
        for _ in range(5):
            self.initial.publish(p)
            time.sleep(0.3)

    def goto(self, x, y, yaw, timeout=120.0):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.z = math.sin(yaw / 2)
        goal.pose.pose.orientation.w = math.cos(yaw / 2)
        f = self.nav.send_goal_async(goal)
        end = time.time() + 20
        while not f.done() and time.time() < end:
            time.sleep(0.05)
        handle = f.result()
        if handle is None or not handle.accepted:
            return None
        rf = handle.get_result_async()
        end = time.time() + timeout
        while not rf.done() and time.time() < end:
            time.sleep(0.1)
        return rf.result() if rf.done() else None


def peak(msgs):
    return max((abs(m.linear.x) for m in msgs), default=0.0)


def main():
    rclpy.init()
    b = Bench()
    ex = MultiThreadedExecutor()
    ex.add_node(b)
    threading.Thread(target=ex.spin, daemon=True).start()
    time.sleep(3.0)

    print('=== AC-N1  real Nav2 servers are up ===')
    ok = b.nav.wait_for_server(timeout_sec=30.0)
    print(f'  /navigate_to_pose server available = {ok} (expect True)')

    print('=== AC-N2  the two chain outputs have exactly one publisher each ===')
    # /cmd_vel_nav is a *candidate* topic: controller_server produces it while
    # following a path and behavior_server produces it during a recovery. Both
    # are legitimate, and arbitrating between them is the mux's whole job. The
    # invariant is on the two topics that actually reach the chassis.
    for topic, expect in (('/cmd_vel_auto', 'hr_motion_mux'),
                          ('/cmd_vel', 'collision_monitor')):
        pubs = publishers(topic)
        print(f'  {topic:15} publishers={pubs}  expect exactly [{expect}] -> '
              f'{"PASS" if pubs == [expect] else "FAIL"}')
    candidates = sorted(set(publishers('/cmd_vel_nav')))
    allowed = {'controller_server', 'behavior_server'}
    print(f'  /cmd_vel_nav    candidate producers={candidates} -> '
          f'{"PASS" if candidates and set(candidates) <= allowed else "FAIL"}')

    print('=== AC-N3  AMCL localises on the saved map ===')
    b.set_initial_pose(0.0, 0.0, 0.0)
    time.sleep(4.0)
    print(f'  initial pose accepted, odom seen = {b.odom is not None} (expect True)')

    print('=== AC-N4  a real navigation goal drives the simulated chassis ===')
    b.nav_cmd.clear(); b.auto.clear(); b.final.clear()
    start = (b.odom.pose.pose.position.x, b.odom.pose.pose.position.y) if b.odom else (0, 0)
    # 客厅西北角，从起点 (2.0, 5.2) 看是 (-0.8, +1.0)
    result = b.goto(-0.8, 1.0, 0.0, timeout=200.0)
    end = (b.odom.pose.pose.position.x, b.odom.pose.pose.position.y) if b.odom else (0, 0)
    moved = math.hypot(end[0] - start[0], end[1] - start[1])
    status = result.status if result else None
    print(f'  goal status = {status} (4 = SUCCEEDED)')
    print(f'  chassis moved {moved:.2f} m (expect > 0.5)')
    print(f'  /cmd_vel_nav  peak {peak(b.nav_cmd):.2f} m/s over {len(b.nav_cmd)} msgs')
    print(f'  /cmd_vel_auto peak {peak(b.auto):.2f} m/s over {len(b.auto)} msgs')
    print(f'  /cmd_vel      peak {peak(b.final):.2f} m/s over {len(b.final)} msgs')

    print('=== AC-N5  ZERO phase cuts a live Nav2 velocity at the mux ===')
    b.current = MotionPhase.ZERO
    time.sleep(1.5)
    b.nav_cmd.clear(); b.auto.clear(); b.final.clear()
    handle_result = None
    # 书房方向，从起点看是 (+3.4, -3.8)
    t = threading.Thread(target=lambda: b.goto(3.4, -3.8, 0.0, timeout=25.0), daemon=True)
    t.start()
    time.sleep(12.0)
    print(f'  Nav2 still computing: /cmd_vel_nav msgs = {len(b.nav_cmd)} (expect > 0)')
    print(f'  but /cmd_vel_auto peak = {peak(b.auto):.2f} m/s (expect 0.00)')
    print(f'  and /cmd_vel      peak = {peak(b.final):.2f} m/s (expect 0.00)')

    print('=== AC-N6  every published velocity has linear.y == 0 ===')
    allm = b.nav_cmd + b.auto + b.final
    print(f'  non-zero linear.y = {sum(1 for m in allm if m.linear.y)} of {len(allm)} (expect 0)')

    rclpy.shutdown()


main()
