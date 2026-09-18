from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_arm_driver'))
    # Off by default: the independent servo controller is not selected yet.
    return LaunchDescription([
        DeclareLaunchArgument('enable_arm_driver', default_value='false'),
        Node(package='hr_arm_driver', executable='arm_driver', name='hr_arm_driver',
             parameters=[str(share / 'config' / 'arm_driver.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_arm_driver')), output='screen')])
