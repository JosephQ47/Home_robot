from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_navigation'))
    return LaunchDescription([
        DeclareLaunchArgument('enable_real_navigation', default_value='false'),
        Node(package='nav2_collision_monitor', executable='collision_monitor', name='collision_monitor',
             parameters=[str(share / 'config' / 'collision_monitor.yaml')], remappings=[('cmd_vel_in', '/cmd_vel_auto'), ('cmd_vel_out', '/cmd_vel')],
             condition=IfCondition(LaunchConfiguration('enable_real_navigation')), output='screen')])
