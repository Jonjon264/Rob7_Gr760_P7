"""X30 merged-cloud mapping with locally published sensor frames."""
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _setup(context):
    config = LaunchConfiguration("config_file").perform(context)
    with open(config, encoding="utf-8") as stream:
        mapping = yaml.safe_load(stream)["/**"]["ros__parameters"]["mapping"]
    if mapping["extrinsic_R"] != [1, 0, 0, 0, 1, 0, 0, 0, 1]:
        raise ValueError("This launch requires the aligned central-IMU rotation")
    translation = mapping["extrinsic_T"]
    sim_time = ParameterValue(LaunchConfiguration("use_sim_time"), value_type=bool)

    def static(name, parent, child, xyz):
        return Node(
            package="tf2_ros", executable="static_transform_publisher", name=name,
            arguments=["--x", str(xyz[0]), "--y", str(xyz[1]), "--z", str(xyz[2]),
                       "--qx", "0", "--qy", "0", "--qz", "0", "--qw", "1",
                       "--frame-id", parent, "--child-frame-id", child],
            parameters=[{"use_sim_time": sim_time}],
            condition=IfCondition(LaunchConfiguration("publish_static_tf")),
            output="screen",
        )

    # FAST-LIO publishes camera_init -> body, where body is its IMU frame.
    # Use the same calibration for both the estimator and the fixed TF chain.
    return [
        static("x30_body_to_base", "body", "base_link", translation),
        static("x30_base_to_imu", "base_link", "imu_link", [-v for v in translation]),
        static("x30_base_to_lidar", "base_link", "lidar_link", [0.0, 0.0, 0.0]),
        # Recorded CustomMsg uses livox_frame for the already-merged points.
        static("x30_base_to_livox", "base_link", "livox_frame", [0.0, 0.0, 0.0]),
        static("x30_base_to_dummy", "base_link", "dummy", [0.0, 0.0, 0.0]),
        static("x30_dummy_to_torso", "dummy", "TORSO", [0.0, 0.0, 0.0]),
        Node(package="fast_lio", executable="fastlio_mapping", name="x30_fastlio",
             parameters=[config, {"use_sim_time": sim_time}], output="screen"),
    ]


def generate_launch_description():
    config = Path(get_package_share_directory("fast_lio")) / "config" / "x30_merged.yaml"
    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value=str(config)),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("publish_static_tf", default_value="true",
                              description="Disable when another ROS2 publisher supplies these frames"),
        OpaqueFunction(function=_setup),
    ])
