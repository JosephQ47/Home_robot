from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_arm_controller'))
    # Off by default: the arm hardware is not fitted yet.
    return LaunchDescription([
        DeclareLaunchArgument('enable_arm', default_value='false'),
        Node(package='hr_arm_controller', executable='arm_controller', name='hr_arm_controller',
             parameters=[str(share / 'config' / 'arm_controller.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_arm')), output='screen')])
