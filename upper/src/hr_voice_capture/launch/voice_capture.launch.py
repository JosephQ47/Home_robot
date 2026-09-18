from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_voice_capture'))
    # Off by default: the USB microphone array is not selected yet.
    return LaunchDescription([
        DeclareLaunchArgument('enable_voice_capture', default_value='false'),
        Node(package='hr_voice_capture', executable='voice_capture', name='hr_voice_capture',
             parameters=[str(share / 'config' / 'voice_capture.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_voice_capture')), output='screen')])
