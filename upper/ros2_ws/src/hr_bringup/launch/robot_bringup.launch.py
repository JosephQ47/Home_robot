from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def source(package, filename):
    return PythonLaunchDescriptionSource(PathJoinSubstitution([FindPackageShare(package), 'launch', filename]))


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('stm32_transport_enabled', default_value='false'),
        DeclareLaunchArgument('command_output_enabled', default_value='false'),
        DeclareLaunchArgument('legacy_firmware_watchdog_verified', default_value='false'),
        DeclareLaunchArgument('bench_motion_authorized', default_value='false'),
        DeclareLaunchArgument('hmmd_transport_enabled', default_value='false'),
        DeclareLaunchArgument('camera_source', default_value='synthetic'),
        DeclareLaunchArgument('perception_backend', default_value='stub'),
        DeclareLaunchArgument('model', default_value=''),
        DeclareLaunchArgument('local_motion_enabled', default_value='false'),
        DeclareLaunchArgument('tracker_mode', default_value='disabled'),
        DeclareLaunchArgument('camera_width_px', default_value='0.0'),
        DeclareLaunchArgument('camera_hfov_rad', default_value='0.0'),
        IncludeLaunchDescription(source('hr_description', 'description.launch.py')),
        IncludeLaunchDescription(source('hr_bridge', 'hr_bridge.launch.py'), launch_arguments={
            'transport_enabled': LaunchConfiguration('stm32_transport_enabled'),
            'command_output_enabled': LaunchConfiguration('command_output_enabled'),
            'legacy_firmware_watchdog_verified': LaunchConfiguration(
                'legacy_firmware_watchdog_verified'),
            'bench_motion_authorized': LaunchConfiguration('bench_motion_authorized')}.items()),
        IncludeLaunchDescription(source('hr_hmmd', 'hmmd.launch.py'), launch_arguments={
            'transport_enabled': LaunchConfiguration('hmmd_transport_enabled')}.items()),
        IncludeLaunchDescription(source('hr_camera', 'camera.launch.py'), launch_arguments={
            'source': LaunchConfiguration('camera_source')}.items()),
        IncludeLaunchDescription(source('hr_perception', 'perception.launch.py'), launch_arguments={
            'backend': LaunchConfiguration('perception_backend'),
            'model': LaunchConfiguration('model')}.items()),
        IncludeLaunchDescription(source('hr_target_tracker', 'tracker.launch.py'), launch_arguments={
            'association_mode': LaunchConfiguration('tracker_mode'),
            'image_width_px': LaunchConfiguration('camera_width_px'),
            'horizontal_fov_rad': LaunchConfiguration('camera_hfov_rad')}.items()),
        IncludeLaunchDescription(source('hr_task_manager', 'task_manager.launch.py')),
        IncludeLaunchDescription(source('hr_local_motion', 'local_motion.launch.py'), launch_arguments={
            'enable': LaunchConfiguration('local_motion_enabled')}.items()),
        IncludeLaunchDescription(source('hr_web_ui', 'web_ui.launch.py')),
    ])
