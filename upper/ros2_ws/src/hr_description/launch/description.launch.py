from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    model = Path(get_package_share_directory('hr_description')) / 'urdf' / 'home_robot.urdf.xacro'
    return LaunchDescription([Node(package='robot_state_publisher', executable='robot_state_publisher',
        parameters=[{'robot_description': model.read_text(encoding='utf-8')}], output='screen')])
