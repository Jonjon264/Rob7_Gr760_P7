# x30_sim

The simulator: launch file, robot model, built-in worlds, and the ROS nodes that
turn Gazebo output into the topics the real X30 provides. Migrated from
`VLA_X30/x30_vln/ros2_ws/src/x30_sim`. Overview of the whole workspace is in
[sim_ws/README.md](../../README.md); setup and run commands are in
[docker/sim/README.md](../../../docker/sim/README.md).

## Layout

```
launch/sim.launch.py     entry point; builds everything and starts all processes
urdf/x30_sim.urdf.xacro  robot: upstream x30_description + sensors
worlds/                  default_arena.sdf, lab_room.sdf
x30_sim/*.py             nodes and helper libraries (below)
test/                    pytest: core maths, nodes, imported world, lock, lidar sync
```

## Build

`ament_python` (`setup.py`). It installs the launch file, xacro, worlds and
`config/`, and registers the node executables as console scripts. Run
dependencies include `x30_msgs`, `x30_worlds`, `x30_description`,
`unitree_guide_controller`, `leg_pd_controller`, `control_input_msgs`,
`ros_gz_sim`, `ros_gz_bridge`, `gz_ros2_control`, `controller_manager`,
`robot_state_publisher`, `xacro`, `python3-tk` (joystick), `numpy`, `yaml`, `opencv`.

```bash
sim-build   # colcon build --symlink-install --packages-up-to x30_msgs x30_worlds x30_sim
```

`--symlink-install` means Python edits apply without rebuilding. A new node,
launch file or data file still needs a rebuild.

## What the launch does

`ros2 launch x30_sim sim.launch.py world:=… locomotion:=…` runs
`launch_setup()` which, in order:

1. takes the single-instance lock (`work_dir`), so two sims cannot share files and topics;
2. loads `robot_sim.yaml` and generates the URDF for the chosen backend;
3. resolves the world, writes a prepared copy of its SDF (absolute paths, needed Gazebo systems, physics step), and writes the `ros_gz_bridge` config. Generated files go to `work_dir` (default `/tmp/x30_sim`);
4. starts `gz sim -s` (server), `robot_state_publisher`, the bridge, and the nodes below;
5. after `spawn_delay` seconds, spawns the robot at the world's spawn pose (or `spawn_x/y/z/yaw`);
6. with `gui:=true`, starts the Gazebo client after the spawn finishes, so it sees the robot;
7. in `legged` mode, brings up the controllers in order: IMU broadcaster, joint state broadcaster, `leg_pd_controller`, then `unitree_guide_controller`.

### Launch arguments

| Argument | Default | Meaning |
|---|---|---|
| `world` | `default_arena` | world id (`aws_hospital`, `default_arena`, `lab_room`) |
| `locomotion` | `kinematic` | `legged` (real gait, needs real-time factor near 1) or `kinematic` (fast, flat floors) |
| `gui` / `joystick` | `false` | Gazebo window / on-screen joystick |
| `render` | `sw` | `sw` Mesa llvmpipe, or `gpu` (WSL2 D3D12) |
| `thermal` / `depth` | `true` | optional thermal camera / sim-only depth image |
| `spawn_x/y/z/yaw` | world's | override start pose |
| `odom_noise` | `0.0` | 0 exact odometry; 1 nominal leg-odometry error; higher scales it |
| `latency` | config | kinematic command latency (s) |
| `rtf`, `seed` | `1.0`, `1` | target real-time factor, noise seed |
| `robot_config`, `registry` | `$X30_CONFIGS/…` | config paths |
| `work_dir`, `mesh_cache`, `spawn_delay` | `/tmp/x30_sim`, `/tmp/x30_sim_meshes`, `6.0` | scratch dirs and delay |

The GUI overlay in `docker/sim` overrides several of these through `SIM_WORLD`,
`SIM_LOCOMOTION`, `SIM_JOYSTICK`.

## Nodes

| Executable | Subscribes | Publishes / provides | Role |
|---|---|---|---|
| `lidar_merge` | `/lidar/{fl,fr,rl,rr}/points` | `/lidar_points` | merges four Livox clouds into the real layout (`x y z intensity f32, tag u8, line u8, timestamp f64`, 26 B/point); invalid rays become a point at the sensor origin |
| `sim_state` | `/gt/odom_raw`, `/x30/estop`, `/clock`, sensor topics (counted) | `/odom`, TF `odom→base_link`, `/gt/pose`, `/x30/battery`, `/x30/health`, `/x30/ready` (kinematic), service `/sim/reset_odom` | robot state outputs; odometry model (see below) |
| `ground_truth` | none | `/gt/objects`, `/gt/scene_info` (latched, once) | world objects parsed from the SDF |
| `sim_services` | `/x30/ready` | services `/sim/set_robot_pose`, `/sim/reset_world` (x30_msgs/Json); `/sim/legged/hold` | episode resets through the `gz service` CLI; never restarts Gazebo |
| `kinematic_driver` | `/cmd_vel`, `/x30/estop` | `/x30/cmd_vel_gz` (bridged to Gazebo VelocityControl) | dead zone, clamp, timeout, latency, acceleration limits, e-stop at 50 Hz |
| `legged_bridge` | `/cmd_vel`, `/x30/estop`, `/sim/legged/hold`, `/rosout` | `/control_input` (control_input_msgs/Inputs), `/x30/ready` | drives the controller's stand-up state machine and gait inputs; reads controller state from its log lines |
| `thermal_processor` | `/thermal/raw` | `/thermal/image_raw` (mono8), `/thermal/temperature` (°C, 32FC1) | converts the raw thermal image |
| `person_mover` | `/clock`, `/sim/person/start`, `/sim/person/reset` | `/gt/person`, `/gt/people` | scripted walking people for follow trials. **Not started by the launch file**; run it yourself |
| `joystick` | none | `/cmd_vel` | Tk on-screen joystick (W/S, A/D, Q/E, space = stop) |

### Gazebo bridge (`bridge_config.py`)

Gazebo to ROS: `/clock`, `/imu/data`, `/camera/color/image_raw`,
`/camera/color/camera_info`, `/gt/odom_raw`, one `/lidar/<id>/points` per
lidar, plus `/camera/depth/image_raw` and `/thermal/raw`, `/thermal/camera_info`
when enabled. ROS to Gazebo (kinematic only): `/x30/cmd_vel_gz` to
`/model/x30/cmd_vel`.

## How odometry works

`sim_state` feeds Gazebo's true base pose (`/gt/odom_raw`) to `LegOdometry` in
`odometry.py`. The first pose becomes the origin; x, y and yaw are kept (leg
odometry on the real robot is planar). Each step's change is rotated into the
previous body frame and integrated. With `odom_noise > 0` it adds a per-run scale
error (2 % translation, 2 % yaw), 5 % per-step noise, and yaw drift of 0.5°/m
plus 0.2°/m noise. These values are assumptions in `robot_sim.yaml`, since the real
robot's drift isn't documented. `odom_noise:=0` gives the exact path, so SLAM
results against it show no drift.

## Source modules

Libraries with no ROS dependency (unit-testable):
`odometry.py`, `lidar_model.py` (cloud layout, self-body mask, intensity, tags),
`lidar_sync.py` (timestamp matching), `geometry.py`, `config.py`,
`mesh_simplify.py` (decimates the 1.3 M-vertex visual meshes, which cost about
100 ms per frame in software rendering), `sdf_scene.py` (object labels from SDF),
`worlds.py` (world lookup and SDF preparation), `robot_description.py` (URDF for
both backends; in kinematic mode the 12 leg joints are frozen standing, gravity
is off and a bumper collision is added), `bridge_config.py`, `gui_config.py`,
`instance_lock.py`.

Helpers for the GUI: `gui_client.py` (connect once the robot's scene exists),
`joystick_gui.py`.

## Locomotion backends

| | `kinematic` | `legged` |
|---|---|---|
| Legs | frozen standing | simulated, `unitree_guide_controller` |
| Speed | fast | needs RTF near 1 |
| Floor | flat only | uneven ok |
| Limits (vx, vy, wz) | ±0.6, ±0.3, ±0.8 | ±0.4, ±0.3, ±0.5 |
| Ready signal | `sim_state` | `legged_bridge` after stand-up |

The legged robot starts at 0.64 m height, falls to its legs, then the bridge
steps the controller from passive to standing to trotting.

## Building on it

- **New sensor**: add it to the xacro and `robot_sim.yaml`, add a bridge entry in
  `bridge_config.py`, and (if the output needs processing) write a node like
  `thermal_processor`.
- **New node**: file in `x30_sim/`, `main()`, entry in `setup.py`, `Node(...)`
  in `sim.launch.py`. Read parameters with `cfgmod.load_robot_config`, and set
  `use_sim_time`.
- **Different odometry or noise**: change `odometry.nominal` in `robot_sim.yaml`
  or `LegOdometry` in `odometry.py`.
- **New world**: see x30_worlds. Built-in single-file worlds can go in `worlds/`.
- **Test**: add to `test/`; run `python3 -m pytest -q /ws/src/x30_sim/test`.
