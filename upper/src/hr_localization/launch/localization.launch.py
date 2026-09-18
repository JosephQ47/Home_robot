"""EKF plus either SLAM or AMCL — never both.

Mapping and AMCL navigation must not run together: each publishes map->odom,
and two publishers of the same transform produce a TF tree that looks fine and
is silently wrong (技术方案 §10.3「节点拓扑」).
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import Node

MODES = ('mock', 'mapping', 'navigation')


def _nodes(context):
    mode = context.launch_configurations['mode']
    if mode not in MODES:
        raise RuntimeError(f'mode must be one of {", ".join(MODES)}')
    if mode == 'mock':
        return []
    share = get_package_share_directory('hr_localization')
    # Real localization is intentionally explicit and will fail clearly if
    # dependencies are absent, rather than degrading to a plausible-looking pose.
    nodes = [Node(package='robot_localization', executable='ekf_node',
                  name='ekf_filter_node', parameters=[share + '/config/ekf.yaml'],
                  output='screen')]
    if mode == 'mapping':
        nodes.append(Node(package='slam_toolbox', executable='async_slam_toolbox_node',
                          name='slam_toolbox',
                          parameters=[share + '/config/slam_toolbox.yaml'],
                          output='screen'))
        return nodes

    # navigation: a frozen map plus AMCL. map_server needs an accepted map, and
    # hr_localization/maps/ is empty until one passes acceptance.
    map_yaml = context.launch_configurations.get('map', '')
    if not map_yaml:
        raise RuntimeError(
            'navigation mode needs map:=<path to an accepted map yaml>; '
            'see hr_localization/maps/README.md')
    managed = ['map_server', 'amcl']
    nodes += [
        Node(package='nav2_map_server', executable='map_server', name='map_server',
             parameters=[{'yaml_filename': map_yaml}], output='screen'),
        Node(package='nav2_amcl', executable='amcl', name='amcl',
             parameters=[share + '/config/amcl.yaml'], output='screen'),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_localization', output='screen',
             parameters=[{'autostart': True, 'bond_timeout': 10.0,
                          'node_names': managed}]),
    ]
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='mock'),
        DeclareLaunchArgument('map', default_value=''),
        OpaqueFunction(function=_nodes),
    ])
