"""Nav2 node group + hr_motion_mux + Collision Monitor.

Order matters and is not cosmetic (技术方案 §3.1.5): the arbitration and the
veto come up before the planners, so there is never a window in which Nav2 is
publishing while nothing is watching the laser.

Everything is off unless `enable_real_navigation:=true`. The default has to be
off while the stop-zone polygon is still empty.
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Brought up in this order, and that is also the order lifecycle_manager
# transitions them.
NAV2_NODES = [
    ('nav2_controller', 'controller_server', 'controller_server'),
    ('nav2_planner', 'planner_server', 'planner_server'),
    ('nav2_behaviors', 'behavior_server', 'behavior_server'),
    ('nav2_bt_navigator', 'bt_navigator', 'bt_navigator'),
    ('nav2_waypoint_follower', 'waypoint_follower', 'waypoint_follower'),
]


def generate_launch_description():
    share = Path(get_package_share_directory('hr_navigation'))
    params = str(share / 'config' / 'nav2_params.yaml')
    enabled = IfCondition(LaunchConfiguration('enable_real_navigation'))

    mux_share = Path(get_package_share_directory('hr_motion_mux'))
    mux = Node(package='hr_motion_mux', executable='motion_mux', name='hr_motion_mux',
               parameters=[str(mux_share / 'config' / 'motion_mux.yaml')],
               condition=enabled, output='screen')

    monitor = Node(package='nav2_collision_monitor', executable='collision_monitor',
                   name='collision_monitor',
                   parameters=[str(share / 'config' / 'collision_monitor.yaml')],
                   remappings=[('cmd_vel_in', '/cmd_vel_auto'), ('cmd_vel_out', '/cmd_vel')],
                   condition=enabled, output='screen')

    nav2 = [Node(package=pkg, executable=exe, name=name, parameters=[params],
                 condition=enabled, output='screen')
            for pkg, exe, name in NAV2_NODES]

    lifecycle = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen', condition=enabled,
        parameters=[{'autostart': LaunchConfiguration('autostart'),
                     'bond_timeout': 10.0,
                     'node_names': [name for _, _, name in NAV2_NODES]}])

    return LaunchDescription([
        DeclareLaunchArgument('enable_real_navigation', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        # Collision Monitor and the mux first: never leave a window where Nav2
        # can publish with nothing watching the laser.
        GroupAction([mux, monitor] + nav2 + [lifecycle]),
    ])
