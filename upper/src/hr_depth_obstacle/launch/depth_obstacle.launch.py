from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_depth_obstacle'))
    return LaunchDescription([
        DeclareLaunchArgument('enable_depth_obstacle', default_value='false'),
        Node(package='hr_depth_obstacle', executable='depth_obstacle', name='hr_depth_obstacle',
             parameters=[str(share / 'config' / 'depth_obstacle.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_depth_obstacle')), output='screen')])
