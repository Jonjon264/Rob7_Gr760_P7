#!/usr/bin/env python3
"""
Example ROS 2 launch file that:
  - declares launch arguments
  - includes launch files from other packages (Python, XML and YAML)
  - starts nodes from different packages
  - groups things under a namespace
  - uses conditions and delayed starts

Replace the package/file/executable names below with your own.
Place this in <your_pkg>/launch/ and make sure the launch dir is installed in setup.py / CMakeLists.txt.
Run with:  ros2 launch <your_pkg> bringup.launch.py use_sim_time:=true
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # ------------------------------------------------------------------
    # Launch arguments (overridable from the command line)
    # ------------------------------------------------------------------
    use_sim_time = LaunchConfiguration("use_sim_time")
    namespace = LaunchConfiguration("namespace")
    launch_rviz = LaunchConfiguration("rviz")

    declared_args = [
        DeclareLaunchArgument(
            "use_sim_time", default_value="false",
            description="Use simulation clock if true",
        ),
        DeclareLaunchArgument(
            "namespace", default_value="",
            description="Namespace for the robot nodes",
        ),
        DeclareLaunchArgument(
            "rviz", default_value="true",
            description="Start RViz",
        ),
    ]

    qwen_launch_file = os.path.join(
        get_package_share_directory("qwen_voice_manager"), "launch", "voice_handler.launch.py"
    )
    qwen_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(qwen_launch_file),
        launch_arguments={
            "use_sim_time": use_sim_time,
        }.items(),
    )

    reach_node = Node(
        package="reach_module",
        executable="reach_publisher",
        name="reach",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time}
        ],
    )

    teach_node = Node(
        package="teach_module",
        executable="teach",
        name="teach",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time}
        ],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=[
            "-d",
            PathJoinSubstitution([
                FindPackageShare("main_bringup"), "config", "default.rviz"
            ]),
        ],
        parameters=[{"use_sim_time": use_sim_time}],
        condition=IfCondition(launch_rviz),  # only if rviz:=true
        output="screen",
    )

    robot_group = GroupAction([
        PushRosNamespace(namespace),
        qwen_launch,
        reach_node,
        teach_node,
    ])

    return LaunchDescription([
        *declared_args,
        LogInfo(msg=["Starting bringup, use_sim_time=", use_sim_time]),
        robot_group,
        rviz_node,
    ])