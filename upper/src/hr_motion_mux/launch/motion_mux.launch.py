from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_motion_mux'))
    return LaunchDescription([
        Node(package='hr_motion_mux', executable='motion_mux', name='hr_motion_mux',
             parameters=[str(share / 'config' / 'motion_mux.yaml')], output='screen')])
