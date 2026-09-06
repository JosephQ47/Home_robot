from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    backend = LaunchConfiguration('backend')
    return LaunchDescription([
        DeclareLaunchArgument('backend', default_value='stub'),
        DeclareLaunchArgument('model', default_value=''),
        Node(package='hr_perception', executable='perception_stub', output='screen',
             condition=UnlessCondition(PythonExpression(["'", backend, "' == 'cpu_yolo'"]))),
        Node(package='hr_perception', executable='perception', name='hr_perception', output='screen',
             parameters=[{'model': LaunchConfiguration('model'), 'require_control': True}],
             condition=IfCondition(PythonExpression(["'", backend, "' == 'cpu_yolo'"]))),
    ])
