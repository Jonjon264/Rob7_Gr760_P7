# X30 mapping workspace

FAST-LIO source, Livox message definitions, configuration, launch files, and
build outputs are all in this workspace. The existing Docker bridge is unchanged.

From `ros2_ws`, build this checkout and launch it in the existing Humble
dependency image:

```bash
docker compose up -d mapper
docker compose logs -f mapper
```

Docker compiles the mounted workspace into `build/` and `install/`, then runs
that build. It does not source the old `/opt/mapping/install` in the image.
The image `livox-mapping-mapper:local` must already be available.
ROS domain defaults to 31, matching the existing Livox bridge; override with
`X30_ROS_DOMAIN_ID` if the bridge uses another domain. Compilation runs serially.

In a sourced ROS2 environment with the dependencies installed, the equivalent is:

```bash
colcon build --merge-install --symlink-install --parallel-workers 1 --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
export ROS_DOMAIN_ID=31
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/cyclonedds.xml"
ros2 launch fast_lio x30.launch.py
```

The X30 configuration is `FAST_LIO_ROS2/config/x30_merged.yaml`. Inputs are the
merged `/livox/lidar` CustomMsg and central `/imu/data`. The original model
configs, including your edited `mid360.yaml`, are preserved.

Calibration assumes `/imu/data` corresponds to the captured `imu_link` pose:
`base_link -> imu_link = [-0.1713, 0, -0.05925]` metres, with aligned axes and
sensor timestamps on the same clock. The recorded bag lacks this central IMU,
so it cannot validate that association or mapping with this input selection.

`x30.launch.py` publishes these fixed frames locally, without robot TF bridging:

```text
camera_init --FAST-LIO--> body --> base_link --> imu_link
                                      |------> lidar_link
                                      |------> livox_frame
                                      `------> dummy --> TORSO
```

FAST-LIO's `body` is its IMU frame. The launch derives the two IMU/base offsets
from the same calibration used by the estimator. Merged points are not
transformed a second time. Set `PUBLISH_STATIC_TF=false` for Docker, or
`publish_static_tf:=false` on the ROS launch command, if another publisher
already supplies these fixed frames. Dynamic leg transforms are not made static.

Outputs include `/Odometry`, `/cloud_registered`, and `/path`, in `camera_init`.
To stop this workspace mapper: `docker compose down` from this directory.
