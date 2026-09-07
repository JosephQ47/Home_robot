"""任务管理启动文件。

超时策略来自 config/task_policy.yaml；mock_navigation_enabled 走 launch 参数
（它决定是否允许在没有地图目标解析器时用模拟导航，属于每次运行的选择）。
本文件原先不加载 yaml，导致 task_policy.yaml 是死配置。

task_timeout_sec 同时存在于 yaml 与 launch 参数：yaml 是基准值，launch 参数
用于单次调试临时覆盖。两者当前同为 30.0。
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    cfg = str(Path(get_package_share_directory('hr_task_manager')) / 'config' / 'task_policy.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('mock_navigation_enabled', default_value='false'),
        DeclareLaunchArgument('task_timeout_sec', default_value='30.0'),
        Node(package='hr_task_manager', executable='task_manager', output='screen',
             parameters=[cfg, {
                 'mock_navigation_enabled': LaunchConfiguration('mock_navigation_enabled'),
                 'task_timeout_sec': LaunchConfiguration('task_timeout_sec'),
             }]),
    ])
