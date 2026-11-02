"""Bag replay: FAST-LIO on merged /livox/lidar + one recorded Livox IMU, sim time."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory("fast_lio")) / "config" / "x30_replay_202.yaml"
    return LaunchDescription([
        Node(package="fast_lio", executable="fastlio_mapping", name="x30_fastlio",
             parameters=[str(config), {"use_sim_time": True}], output="screen"),
    ])
