from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hr_docking'))
    # Off by default: the dock, its tag and the hand-eye offsets are not frozen,
    # so an accidental launch must not be able to drive the robot at a wall.
    return LaunchDescription([
        DeclareLaunchArgument('enable_docking', default_value='false'),
        Node(package='hr_docking', executable='dock_pose_adapter', name='hr_dock_pose_adapter',
             parameters=[str(share / 'config' / 'docks.yaml')],
             condition=IfCondition(LaunchConfiguration('enable_docking')), output='screen')])
