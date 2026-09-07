#!/usr/bin/env python3
"""验证 collision_monitor 的 hmmd 障碍源：三条失效安全判据，用真实雷达。

判据
----
  1. 无 /hmmd/detection 数据时输出零速（数据不新鲜 → 停）。
  2. presence=true 且 range_m <= stop_distance 时输出零速（人太近 → 停）。
  3. range_m 为 NaN（未标定）时输出零速 —— 读不到距离绝不能当成安全。
  4. presence=false 时放行（并被限幅）。

本脚本只发布 /cmd_vel_auto 与合成的 /hmmd/detection，不打开任何真实设备、
不启动 hr_bridge，因此**不可能驱动底盘**。真实雷达仅用于判据 0 的连通性确认。

用法：python3 upper/tools/verify_hmmd_gate.py
"""
import math
import os
import signal
import subprocess
import sys
import time

from geometry_msgs.msg import Twist
from hr_interfaces.msg import HmmdDetection
import rclpy
from rclpy.node import Node

STOP_M = 0.40


class Probe(Node):
    def __init__(self):
        super().__init__('verify_hmmd_gate')
        self.final = []
        self.create_subscription(Twist, '/cmd_vel', lambda m: self.final.append(m), 50)
        self.auto = self.create_publisher(Twist, '/cmd_vel_auto', 10)
        self.hmmd = self.create_publisher(HmmdDetection, '/hmmd/detection', 10)

    def drive(self, linear=0.08, angular=0.05):
        msg = Twist(); msg.linear.x = linear; msg.angular.z = angular
        self.auto.publish(msg)

    def radar(self, presence, range_m):
        msg = HmmdDetection()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'hmmd_link'
        msg.presence = presence
        msg.range_m = range_m
        self.hmmd.publish(msg)


def nonzero(m):
    return abs(m.linear.x) > 1e-5 or abs(m.angular.z) > 1e-5


def pump(node, seconds, radar=None):
    """持续发命令（必要时也发雷达帧），返回该窗口内收到的 /cmd_vel。"""
    node.final.clear()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        node.drive()
        if radar is not None:
            node.radar(*radar)
        rclpy.spin_once(node, timeout_sec=0.02)
    return list(node.final)


def main():
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '71')
    os.environ['ROS_DOMAIN_ID'] = env['ROS_DOMAIN_ID']
    launch = subprocess.Popen(
        ['ros2', 'launch', 'hr_navigation', 'validation_collision.launch.py',
         'obstacle_source:=hmmd', f'stop_distance_m:={STOP_M}'],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True)
    rclpy.init()
    node = Probe()
    try:
        # 等**订阅**出现，而不是等节点名出现。
        # 节点名在 super().__init__() 里就注册了，而订阅是之后才创建的 ——
        # 一看到名字就去查订阅必然查早，这是本仓已经踩过三次的同一类竞态。
        deadline = time.monotonic() + 25.0
        subscribed = False
        while time.monotonic() < deadline and not subscribed:
            rclpy.spin_once(node, timeout_sec=0.05)
            subscribed = any(info.node_name == 'collision_monitor'
                             for info in node.get_subscriptions_info_by_topic('/hmmd/detection'))
        if not subscribed:
            if 'collision_monitor' not in node.get_node_names():
                raise RuntimeError('collision_monitor 未启动')
            raise RuntimeError('collision_monitor 已启动但未订阅 /hmmd/detection'
                               ' —— obstacle_source 没生效')

        # 判据 1：只发命令、不发雷达 → 数据不新鲜 → 必须零速
        out = pump(node, 1.5)
        if not out or any(nonzero(m) for m in out[-10:]):
            raise RuntimeError('无雷达数据时未输出零速（失效安全失败）')

        # 判据 2：人在 0.20 m（小于停止距离）→ 必须零速
        out = pump(node, 1.2, radar=(True, 0.20))
        if not out or any(nonzero(m) for m in out[-10:]):
            raise RuntimeError('人在停止距离内时未停车')

        # 判据 3：range_m 为 NaN（未标定）→ 必须零速
        out = pump(node, 1.2, radar=(True, float('nan')))
        if not out or any(nonzero(m) for m in out[-10:]):
            raise RuntimeError('距离不可用（NaN）时未停车 —— 读不到距离被当成了安全')

        # 判据 4：无人 → 放行，且被限幅
        out = pump(node, 1.2, radar=(False, float('nan')))
        moving = [m for m in out if nonzero(m)]
        if not moving:
            raise RuntimeError('无人时未放行')
        if max(abs(m.linear.x) for m in moving) > 0.1001:
            raise RuntimeError('放行时线速度超过限幅')

        # 判据 5：人在 2.0 m（大于停止距离）→ 放行
        out = pump(node, 1.2, radar=(True, 2.0))
        if not any(nonzero(m) for m in out):
            raise RuntimeError('人在停止距离外时未放行')

        print('PASS: hmmd 障碍源五条判据全过 —— '
              '无数据停、人太近停、距离 NaN 停、无人放行且限幅、人在远处放行')
        print('SAFE: 未启动 hr_bridge，未打开任何设备，不可能驱动底盘')
        print('注意: hmmd 模式只检测人体微动，看不见墙与家具。它不是避障。')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        launch.send_signal(signal.SIGINT)
        try:
            output, _ = launch.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
            output, _ = launch.communicate()
        if 'Traceback (most recent call last)' in output:
            print(output)
            raise RuntimeError('collision monitor 未干净退出')


if __name__ == '__main__':
    sys.exit(main() or 0)
