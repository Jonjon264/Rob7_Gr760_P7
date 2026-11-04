"""AI task pipeline for the simulator: Qwen voice/text manager -> task handler -> Nav2 executor."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    default_map = get_package_share_directory('qwen_voice_manager') + '/config/map.json'
    use_sim_time = ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)
    map_file = ParameterValue(LaunchConfiguration('map_file'), value_type=str)
    map_yaml = ParameterValue(LaunchConfiguration('map_yaml'), value_type=str)
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('map_file', default_value=default_map,
                              description='places file read by Qwen and edited by teach requests'),
        DeclareLaunchArgument('map_yaml', default_value='',
                              description='map yaml the waypoints were labelled on; converts pixels to metres'),
        DeclareLaunchArgument('speech_enabled', default_value='false'),
        DeclareLaunchArgument('wake_words', default_value='bumblebee'),
        DeclareLaunchArgument('input_device_index', default_value='-1'),
        Node(package='robot_task_handler', executable='handler', output='screen',
             parameters=[{'use_sim_time': use_sim_time}]),
        Node(
            package='qwen_voice_manager', executable='voice_manager', output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'map_file': map_file,
                'speech_enabled': ParameterValue(LaunchConfiguration('speech_enabled'), value_type=bool),
                'wake_words': ParameterValue(LaunchConfiguration('wake_words'), value_type=str),
                'input_device_index': ParameterValue(LaunchConfiguration('input_device_index'), value_type=int),
            }],
        ),
        Node(package='x30_task_executor', executable='executor', output='screen',
             parameters=[{'use_sim_time': use_sim_time, 'map_file': map_file, 'map_yaml': map_yaml}]),
    ])
