from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    cfg = str(Path(get_package_share_directory('hr_local_motion')) / 'config' / 'local_motion.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('enable', default_value='false'),
        DeclareLaunchArgument('required_downstream_node', default_value='collision_monitor'),
        Node(package='hr_local_motion', executable='local_motion',
             name='nav2_local_controller_adapter', output='screen',
             parameters=[cfg, {'output_enabled': True,
                               'required_downstream_node': ParameterValue(
                                   LaunchConfiguration('required_downstream_node'), value_type=str)}],
             condition=IfCondition(LaunchConfiguration('enable')))])
