from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([Node(package='hr_web_ui', executable='ros_adapter', output='screen')])
