from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node


def _nodes(context):
    mode = context.launch_configurations['mode']
    if mode not in ('mock', 'mapping', 'navigation'):
        raise RuntimeError('mode must be mock, mapping, or navigation')
    if mode == 'mock':
        return []
    share = get_package_share_directory('hr_localization')
    # Real localization is intentionally explicit and will fail clearly if dependencies are absent.
    nodes = [Node(package='robot_localization', executable='ekf_node', name='ekf_filter_node',
                  parameters=[share + '/config/ekf.yaml'], output='screen')]
    if mode == 'mapping':
        nodes.append(Node(package='slam_toolbox', executable='async_slam_toolbox_node', name='slam_toolbox', output='screen'))
    return nodes


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('mode', default_value='mock'), OpaqueFunction(function=_nodes)])
