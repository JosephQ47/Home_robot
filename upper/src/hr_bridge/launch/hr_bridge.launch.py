from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("port", default_value="/dev/robot_mcu"),
            DeclareLaunchArgument("baud", default_value="230400"),
            DeclareLaunchArgument("transport_enabled", default_value="false"),
            DeclareLaunchArgument("command_output_enabled", default_value="false"),
            DeclareLaunchArgument("legacy_firmware_watchdog_verified", default_value="false"),
            DeclareLaunchArgument("bench_motion_authorized", default_value="false"),
            Node(
                package="hr_bridge",
                executable="hr_bridge",
                name="hr_bridge",
                output="screen",
                parameters=[{"port": LaunchConfiguration("port"), "baud": LaunchConfiguration("baud"),
                             "transport_enabled": ParameterValue(LaunchConfiguration("transport_enabled"), value_type=bool),
                             "command_output_enabled": ParameterValue(LaunchConfiguration("command_output_enabled"), value_type=bool),
                             "legacy_firmware_watchdog_verified": ParameterValue(
                                 LaunchConfiguration("legacy_firmware_watchdog_verified"), value_type=bool),
                             "bench_motion_authorized": ParameterValue(
                                 LaunchConfiguration("bench_motion_authorized"), value_type=bool)}],
            ),
        ]
    )
