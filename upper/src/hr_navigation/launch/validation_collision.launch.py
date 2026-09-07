"""Collision Monitor 替身的启动文件。

obstacle_source 决定它拿什么判「前方是否可走」：
  scan （默认）二维激光扫描 —— 技术方案 §3.5 的正式方案。
  hmmd  毫米波 —— 没有激光雷达时的临时替代，只能判「有人靠太近」，
        看不见墙和家具，详见 collision_monitor_adapter.py 的文件头。
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('obstacle_source', default_value='scan'),
        DeclareLaunchArgument('stop_distance_m', default_value='0.40'),
        Node(package='hr_navigation', executable='collision_monitor_adapter.py',
             name='collision_monitor', output='screen', parameters=[{
                 'output_enabled': True,
                 'obstacle_source': LaunchConfiguration('obstacle_source'),
                 # 不是冻结的物理停止距离，实车前须按制动实测重定。
                 'stop_distance_m': LaunchConfiguration('stop_distance_m'),
                 'scan_timeout_sec': 0.30,
                 'command_timeout_sec': 0.20,
                 'max_linear_mps': 0.10,
                 'max_angular_rps': 0.30,
             }])
    ])
