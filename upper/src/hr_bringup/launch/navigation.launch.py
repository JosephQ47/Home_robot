from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def include(package, filename, arguments=None):
    return IncludeLaunchDescription(PythonLaunchDescriptionSource(
        PathJoinSubstitution([FindPackageShare(package), 'launch', filename])),
        launch_arguments=(arguments or {}).items())


def generate_launch_description():
    return LaunchDescription([
        include('hr_localization', 'localization.launch.py', {'mode': 'navigation'}),
        include('hr_navigation', 'navigation.launch.py', {'enable_real_navigation': 'true'}),
    ])
