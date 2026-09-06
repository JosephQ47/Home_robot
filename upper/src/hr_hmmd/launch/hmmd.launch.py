"""HMMD 毫米波驱动启动文件。

参数分两类，来源不同，不要混：
  · 标定与门限（range_scale_m、stale_after_sec…）来自 config/hmmd.yaml，
    它们是**实测常量**，改了要留证据，不该在命令行随手改。
  · 每次运行才决定的（transport_enabled、port）走 launch 参数覆盖 yaml。

本文件原先根本不加载 yaml，range_scale_m 的 launch 默认值写死 0.0 ——
于是把标定写进 config/hmmd.yaml 完全不生效，且不报任何错。
这一类「配置看着权威、其实是死的」问题由 upper/tools/verify_config_wiring.py 拦截。
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    cfg = str(Path(get_package_share_directory('hr_hmmd')) / 'config' / 'hmmd.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('transport_enabled', default_value='false'),
        DeclareLaunchArgument('port', default_value='/dev/hmmd_radar'),
        Node(package='hr_hmmd', executable='hmmd_node', name='hmmd_radar_driver',
             output='screen',
             parameters=[cfg, {
                 # 只覆盖「每次运行才决定」的两项；其余一律以 yaml 为准。
                 'transport_enabled': ParameterValue(
                     LaunchConfiguration('transport_enabled'), value_type=bool),
                 'port': LaunchConfiguration('port')}])])
