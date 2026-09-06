from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mock_navigation_enabled', default_value='false'),
        DeclareLaunchArgument('task_timeout_sec', default_value='30.0'),
        Node(package='hr_task_manager', executable='task_manager', output='screen', parameters=[{
            'mock_navigation_enabled': LaunchConfiguration('mock_navigation_enabled'),
            'task_timeout_sec': LaunchConfiguration('task_timeout_sec'),
        }]),
    ])
