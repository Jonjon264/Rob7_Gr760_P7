import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def static_tf(x, y, z, roll, pitch, yaw, parent, child):
    """Helper that builds a static_transform_publisher node."""
    return Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name=f"static_tf_{parent}_to_{child}",
        arguments=[
            "--x", str(x), "--y", str(y), "--z", str(z),
            "--roll", str(roll), "--pitch", str(pitch), "--yaw", str(yaw),
            "--frame-id", parent,
            "--child-frame-id", child,
        ],
        output="screen",
    )


def generate_launch_description():
    fast_lio_share = get_package_share_directory("fast_lio")

    # ---- Launch arguments (forwarded to fast_lio's mapping.launch.py) ----
    use_sim_time = LaunchConfiguration("use_sim_time")
    config_path = LaunchConfiguration("config_path")
    config_file = LaunchConfiguration("config_file")
    rviz = LaunchConfiguration("rviz")

    declare_args = [
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument(
            "config_path",
            default_value=os.path.join(fast_lio_share, "config"),
        ),
        DeclareLaunchArgument("config_file", default_value="mid360.yaml"),
        DeclareLaunchArgument("rviz", default_value="true"),
    ]

    # ---- FAST-LIO mapping ----
    fast_lio_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(fast_lio_share, "launch", "mapping.launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "config_path": config_path,
            "config_file": config_file,
            "rviz": rviz,
        }.items(),
    )

    # ---- Static transforms (edit to match your robot) ----
    # FAST-LIO publishes camera_init -> body, so tie camera_init to your world
    # frame and body to the robot's base frame.
    static_tfs = [
        # x, y, z, roll, pitch, yaw, parent, child
        static_tf(0, 0, 0, 0, 0, 0, "body", "base_link"),
    ]

    return LaunchDescription(declare_args + static_tfs + [fast_lio_launch])