from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('publish_robot_status', default_value='true'),
        Node(package='hr_simulation', executable='mock_system', output='screen', parameters=[{
            'publish_robot_status': ParameterValue(
                LaunchConfiguration('publish_robot_status'), value_type=bool),
        }]),
    ])
