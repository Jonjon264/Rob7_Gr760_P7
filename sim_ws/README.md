# sim_ws: X30 simulator workspace

ROS 2 Jazzy / Gazebo Harmonic simulation of the DEEP Robotics X30. This is a
separate workspace from the Humble robot stack in `ros2_ws`. How to build the
image and start it is in [docker/sim/README.md](../docker/sim/README.md); this
page explains what is in the workspace and how the pieces fit.

## Packages

| Package | Build type | Purpose | Details |
|---|---|---|---|
| [x30_msgs](src/x30_msgs/README.md) | ament_cmake | Custom messages, services, actions | interface definitions |
| [x30_sim](src/x30_sim/README.md) | ament_python | Launch file, robot model, nodes | the simulator itself |
| [x30_worlds](src/x30_worlds/README.md) | ament_cmake | Gazebo worlds, models, ground-truth data | `aws_hospital` |
| [x30_navigation](src/x30_navigation/README.md) | ament_cmake | Nav2, mapping, FAST-LIO localization | `navigation.launch.py` |
| [x30_task_executor](src/x30_task_executor/README.md) | ament_python | AI task goals/cancel/teach to Nav2 | `ai_tasks.launch.py` |
| interfaces, robot_task_handler, qwen_voice_manager | mixed | Qwen voice/text to task messages (copied from the AI repo) | see x30_task_executor |

Dependency order: `x30_msgs` and `x30_worlds` first, then `x30_sim` (it
`exec_depend`s on both). `sim-build` builds all three with
`colcon build --packages-up-to x30_msgs x30_worlds x30_sim`.

Not in this workspace but required, and built into the image at
`/opt/x30_ext`: `x30_description`, `unitree_guide_controller`,
`leg_pd_controller`, `controller_common` and `control_input_msgs` from the
upstream `quadruped_ros2_control` repository (pinned commit, plus
`docker/sim/patches/unitree_guide_x30.patch`).

Configuration is outside the packages, in `configs/sim/`
(`robot_sim.yaml`, `worlds.yaml`). In the container it is at `/x30/configs/sim`
(`X30_CONFIGS`). Sensor mounts, rates, noise, topic names, frames and velocity
limits are all set there, so most tuning needs no code change.

## How the pieces fit

```
configs/sim/robot_sim.yaml ──┐
configs/sim/worlds.yaml ─────┤
                             ▼
 sim.launch.py ── builds URDF (xacro) + world SDF + bridge.yaml into /tmp/x30_sim
      │
      ├─ gz sim (server)  ◄── world from x30_worlds / x30_sim, robot spawned via ros_gz_sim
      ├─ ros_gz_bridge    ◄── Gazebo topics ⇄ ROS topics (/clock, IMU, camera, per-lidar clouds, /gt/odom_raw)
      ├─ robot_state_publisher, static TF base_link → base
      ├─ x30_sim nodes    ◄── lidar_merge, sim_state, ground_truth, sim_services,
      │                       thermal_processor (optional), joystick (optional)
      └─ locomotion backend (one of):
           kinematic: kinematic_driver ─► Gazebo VelocityControl (no legs, fast)
           legged:    legged_bridge ─► unitree_guide_controller via ros2_control (real gait)
```

Both backends take `/cmd_vel` and expose the same sensor and state topics, so
code that uses the simulator does not care which one runs.

## Topic contract (what a consumer sees)

Outputs:

| Topic | Type | Rate | From |
|---|---|---|---|
| `/clock` | rosgraph_msgs/Clock | sim | Gazebo |
| `/lidar_points` | sensor_msgs/PointCloud2 | 10 Hz | `lidar_merge` (4 Livox merged, 26-byte points) |
| `/imu/data` | sensor_msgs/Imu | 200 Hz | Gazebo IMU |
| `/odom`, TF `odom→base_link` | nav_msgs/Odometry | 50 Hz | `sim_state` |
| `/camera/color/image_raw`, `/camera/color/camera_info` | Image, CameraInfo | 10 Hz | Gazebo camera |
| `/camera/depth/image_raw` | Image | 10 Hz | Gazebo RGB-D (sim only, `depth:=true`) |
| `/thermal/image_raw`, `/thermal/temperature`, `/thermal/camera_info` | Image, Image, CameraInfo | 5 Hz | `thermal_processor` (`thermal:=true`) |
| `/x30/ready`, `/x30/battery`, `/x30/health` | Bool, BatteryState, DiagnosticArray | | `sim_state`, `legged_bridge` |
| `/gt/pose`, `/gt/objects`, `/gt/scene_info` | PoseStamped, SemanticObjectArray, String | | `sim_state`, `ground_truth` |

Inputs:

| Topic | Type | Effect |
|---|---|---|
| `/cmd_vel` | geometry_msgs/Twist | body-frame velocity (limits below) |
| `/x30/estop` | std_msgs/Bool | instant zero velocity |
| `/sim/reset_odom` | std_srvs/Trigger | new odom origin at the next pose |
| `/sim/set_robot_pose`, `/sim/reset_world` | x30_msgs/Json | episode reset (see x30_sim) |

Velocity limits: `legged` ±0.4 m/s forward, ±0.3 sideways, ±0.5 rad/s;
`kinematic` ±0.6, ±0.3, ±0.8. `/cmd_vel` is zeroed after 0.5 s of silence.

Topic names and frames come from `robot_sim.yaml`; the table shows defaults.

## Build and test

```bash
sim-build                                  # inside the container, rebuilds the three packages
python3 -m pytest -q /ws/src/x30_sim/test  # unit and node tests
```

Build outputs live in the `sim_build`, `sim_install` and `sim_log` Docker
volumes, so they never mix with the Humble workspace. After rebuilding the
image, run `sim-build` once to refresh them.

## Building on it

- **Tune the robot or sensors**: edit `configs/sim/robot_sim.yaml`; no rebuild needed for the
  container, because `configs/` is mounted at `/x30`. (The image also copies it at build time.)
- **Add a world**: see the x30_worlds page. Register it in `configs/sim/worlds.yaml`.
- **Add a node**: write it in `x30_sim/x30_sim/`, add a console script in
  `setup.py`, start it from `sim.launch.py`, then `sim-build`.
- **Navigate with Nav2 or SLAM**: see [x30_navigation](src/x30_navigation/README.md). `x30_fastlio` adapts the
  `PointCloud2` to the Livox message FAST-LIO reads.
- **Connect to the Humble stack**: a separate integration step (ROS domain 10 is
  used here by default, `SIM_ROS_DOMAIN_ID`).
- **Add interfaces**: add the file to `x30_msgs` and its `CMakeLists.txt`.
