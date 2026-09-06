from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def source(package, filename):
    return PythonLaunchDescriptionSource(PathJoinSubstitution([FindPackageShare(package), 'launch', filename]))


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('source', description='RTSP URL confirmed for this session'),
        DeclareLaunchArgument('backend', default_value='stub'),
        DeclareLaunchArgument('model', default_value=''),
        IncludeLaunchDescription(source('hr_camera', 'camera.launch.py'),
                                 launch_arguments={'source': LaunchConfiguration('source')}.items()),
        IncludeLaunchDescription(source('hr_perception', 'perception.launch.py'),
                                 launch_arguments={'backend': LaunchConfiguration('backend'),
                                                   'model': LaunchConfiguration('model')}.items()),
        IncludeLaunchDescription(source('hr_target_tracker', 'tracker.launch.py')),
    ])
