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
# transitions them. collision_monitor is managed alongside them even though it
# is not a planner: it is a lifecycle node, and leaving it out of node_names
# means it sits unconfigured forever while every other node reports healthy —
# the laser veto would simply never run, and nothing would say so.
# (package, executable, node name, remappings)
#
# The remapping on controller_server and behavior_server is the single most
# important line in this file. Both of them publish to a topic literally named
# "cmd_vel", and in Humble the controller's `cmd_vel_topic` parameter is not
# read at all — setting it in nav2_params.yaml looks like it works and does
# nothing. Without the remap the controller and every recovery behaviour write
# straight onto the final /cmd_vel, bypassing hr_motion_mux and the Collision
# Monitor completely: the robot then drives during a ZERO phase and drives
# through a laser stop zone, with no error anywhere.
NAV2_NODES = [
    ('nav2_controller', 'controller_server', 'controller_server',
     [('cmd_vel', '/cmd_vel_nav')]),
    ('nav2_planner', 'planner_server', 'planner_server', []),
    ('nav2_behaviors', 'behavior_server', 'behavior_server',
     [('cmd_vel', '/cmd_vel_nav')]),
    ('nav2_bt_navigator', 'bt_navigator', 'bt_navigator', []),
    ('nav2_waypoint_follower', 'waypoint_follower', 'waypoint_follower', []),
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
                 remappings=remaps, condition=enabled, output='screen')
            for pkg, exe, name, remaps in NAV2_NODES]

    # The veto transitions first and shuts down last.
    managed = ['collision_monitor'] + [name for _, _, name, _ in NAV2_NODES]

    lifecycle = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen', condition=enabled,
        parameters=[{'autostart': LaunchConfiguration('autostart'),
                     'bond_timeout': 10.0,
                     'node_names': managed}])

    return LaunchDescription([
        DeclareLaunchArgument('enable_real_navigation', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        # Collision Monitor and the mux first: never leave a window where Nav2
        # can publish with nothing watching the laser.
        GroupAction([mux, monitor] + nav2 + [lifecycle]),
    ])
