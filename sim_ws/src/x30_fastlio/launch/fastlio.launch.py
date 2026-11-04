import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('x30_fastlio'), 'config', 'x30_sim.yaml')
    rviz_cfg = os.path.join(get_package_share_directory('fast_lio'), 'rviz', 'fastlio.rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='false'),
        DeclareLaunchArgument('localizer', default_value='true',
                              description='publish map->odom from FAST-LIO (turn off while SLAM Toolbox owns map->odom)'),
        Node(
            package='x30_fastlio',
            executable='livox_adapter',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen',
        ),
        Node(
            package='fast_lio',
            executable='fastlio_mapping',
            parameters=[config, {'use_sim_time': use_sim_time}],
            output='screen',
        ),
        Node(
            package='x30_fastlio',
            executable='fastlio_localizer',
            parameters=[{'use_sim_time': use_sim_time}],
            condition=IfCondition(LaunchConfiguration('localizer')),
            output='screen',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_cfg],
            parameters=[{'use_sim_time': use_sim_time}],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
