from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('source', default_value='synthetic'),
        DeclareLaunchArgument('capture_width', default_value='0'),
        DeclareLaunchArgument('capture_height', default_value='0'),
        DeclareLaunchArgument('capture_fps', default_value='0.0'),
        DeclareLaunchArgument('pixel_format', default_value=''),
        Node(package='hr_vision', executable='image_source', name='hi3516_camera_driver', output='screen',
             parameters=[{'source': LaunchConfiguration('source'),
                          'capture_width': ParameterValue(LaunchConfiguration('capture_width'), value_type=int),
                          'capture_height': ParameterValue(LaunchConfiguration('capture_height'), value_type=int),
                          'capture_fps': ParameterValue(LaunchConfiguration('capture_fps'), value_type=float),
                          'pixel_format': ParameterValue(LaunchConfiguration('pixel_format'), value_type=str)}])])
