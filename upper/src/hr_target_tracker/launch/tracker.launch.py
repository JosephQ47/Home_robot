"""目标跟踪启动文件。

参数分两类：门限与策略来自 config/tracker.yaml（改了要留依据），
相机内参与关联模式走 launch 参数（每次运行/每台设备才决定）。
本文件原先不加载 yaml，导致 tracker.yaml 是死配置。
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    cfg = str(Path(get_package_share_directory('hr_target_tracker')) / 'config' / 'tracker.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('association_mode', default_value='disabled'),
        DeclareLaunchArgument('image_width_px', default_value='0.0'),
        DeclareLaunchArgument('horizontal_fov_rad', default_value='0.0'),
        Node(package='hr_target_tracker', executable='target_tracker', output='screen',
             parameters=[cfg, {
                 'association_mode': LaunchConfiguration('association_mode'),
                 'image_width_px': ParameterValue(
                     LaunchConfiguration('image_width_px'), value_type=float),
                 'horizontal_fov_rad': ParameterValue(
                     LaunchConfiguration('horizontal_fov_rad'), value_type=float),
             }])])
