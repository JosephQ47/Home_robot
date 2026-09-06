from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def include(package, filename, arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([FindPackageShare(package), 'launch', filename])),
        launch_arguments=(arguments or {}).items())


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('bridge_port', default_value='/dev/robot_mcu'),
        DeclareLaunchArgument('bridge_transport_enabled', default_value='false'),
        DeclareLaunchArgument('bridge_command_output_enabled', default_value='false'),
        DeclareLaunchArgument('legacy_firmware_watchdog_verified', default_value='false'),
        DeclareLaunchArgument('bench_motion_authorized', default_value='false'),
        DeclareLaunchArgument('publish_mock_robot_status', default_value='true'),
        include('hr_description', 'description.launch.py'),
        include('hr_simulation', 'simulation.launch.py', {
            'publish_robot_status': LaunchConfiguration('publish_mock_robot_status')}),
        include('hr_bridge', 'hr_bridge.launch.py', {
            'port': LaunchConfiguration('bridge_port'),
            'transport_enabled': LaunchConfiguration('bridge_transport_enabled'),
            'command_output_enabled': LaunchConfiguration('bridge_command_output_enabled'),
            'legacy_firmware_watchdog_verified': LaunchConfiguration(
                'legacy_firmware_watchdog_verified'),
            'bench_motion_authorized': LaunchConfiguration('bench_motion_authorized')}),
        include('hr_navigation', 'validation_collision.launch.py'),
        include('hr_local_motion', 'local_motion.launch.py', {'enable': 'true'}),
    ])
