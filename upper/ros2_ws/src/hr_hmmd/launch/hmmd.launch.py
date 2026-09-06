from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('transport_enabled', default_value='false'),
        DeclareLaunchArgument('port', default_value='/dev/hmmd_radar'),
        DeclareLaunchArgument('baud', default_value='115200'),
        DeclareLaunchArgument('range_scale_m', default_value='0.0'),
        DeclareLaunchArgument('configure_report_mode', default_value='true'),
        Node(package='hr_hmmd', executable='hmmd_node', name='hmmd_radar_driver',
             output='screen', parameters=[{
            'transport_enabled': ParameterValue(LaunchConfiguration('transport_enabled'), value_type=bool),
            'port': LaunchConfiguration('port'),
            'baud': ParameterValue(LaunchConfiguration('baud'), value_type=int),
            'range_scale_m': ParameterValue(LaunchConfiguration('range_scale_m'), value_type=float),
            'configure_report_mode': ParameterValue(
                LaunchConfiguration('configure_report_mode'), value_type=bool)}])])
