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
        include('hr_description', 'description.launch.py'),
        include('hr_simulation', 'simulation.launch.py'),
        include('hr_hmmd', 'hmmd.launch.py'),
        include('hr_camera', 'camera.launch.py'),
        include('hr_perception', 'perception.launch.py'),
        include('hr_target_tracker', 'tracker.launch.py'),
        include('hr_task_manager', 'task_manager.launch.py', {'mock_navigation_enabled': 'true'}),
        include('hr_web_ui', 'web_ui.launch.py'),
    ])
