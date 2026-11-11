import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('speech_enabled', default_value='true'),
        DeclareLaunchArgument('wake_words', default_value='hey_jarvis'),
        DeclareLaunchArgument('input_device_index', default_value='-1'),
        DeclareLaunchArgument('tts_enabled', default_value='true'),
        DeclareLaunchArgument('tts_model', default_value=os.path.expanduser(
            '~/ros2_ws/config/piper/en_US-hfc_male-medium.onnx')),
        DeclareLaunchArgument('output_device_index', default_value='-1'),
        Node(package='robot_task_handler', executable='handler', output='screen'),
        Node(
            package='qwen_voice_manager', executable='voice_manager', output='screen',
            parameters=[{
                'speech_enabled': ParameterValue(LaunchConfiguration('speech_enabled'), value_type=bool),
                'wake_words': ParameterValue(LaunchConfiguration('wake_words'), value_type=str),
                'input_device_index': ParameterValue(LaunchConfiguration('input_device_index'), value_type=int),
                'tts_enabled': ParameterValue(LaunchConfiguration('tts_enabled'), value_type=bool),
                'tts_model': LaunchConfiguration('tts_model'),
                'output_device_index': ParameterValue(LaunchConfiguration('output_device_index'), value_type=int),
            }],
        ),
    ])
