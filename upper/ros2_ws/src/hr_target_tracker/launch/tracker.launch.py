from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('association_mode', default_value='disabled'),
        DeclareLaunchArgument('image_width_px', default_value='0.0'),
        DeclareLaunchArgument('horizontal_fov_rad', default_value='0.0'),
        Node(package='hr_target_tracker', executable='target_tracker', output='screen', parameters=[{
            'association_mode': LaunchConfiguration('association_mode'),
            'image_width_px': ParameterValue(LaunchConfiguration('image_width_px'), value_type=float),
            'horizontal_fov_rad': ParameterValue(LaunchConfiguration('horizontal_fov_rad'), value_type=float),
        }])])
