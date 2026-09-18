from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_arm_perception'))
    # Off by default: the D435i and its hand-eye calibration do not exist yet.
    return LaunchDescription([
        DeclareLaunchArgument('enable_arm_perception', default_value='false'),
        Node(package='hr_arm_perception', executable='arm_perception', name='hr_arm_perception',
             parameters=[str(share / 'config' / 'arm_perception.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_arm_perception')), output='screen')])
