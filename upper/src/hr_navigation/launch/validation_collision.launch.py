from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='hr_navigation', executable='collision_monitor_adapter.py',
             name='collision_monitor', output='screen', parameters=[{
                 'output_enabled': True,
                 # Mock-only value. It is not a frozen physical stop distance.
                 'stop_distance_m': 0.40,
                 'scan_timeout_sec': 0.30,
                 'command_timeout_sec': 0.20,
                 'max_linear_mps': 0.10,
                 'max_angular_rps': 0.30,
             }])
    ])
