# x30_navigation

Nav2 for the simulated X30, with FAST-LIO as the localizer. Start the simulator first
(`x30_sim sim.launch.py`), then one of:

```bash
# 1. Map a world: drive with the joystick (or send Nav2 goals), then save
ros2 launch x30_navigation navigation.launch.py mode:=mapping
ros2 run x30_navigation save_map aws_hospital          # -> configs/maps/aws_hospital/map.{yaml,pgm}

# 2. Navigate on the saved map
ros2 launch x30_navigation navigation.launch.py mode:=navigation world:=aws_hospital
```

Both modes also accept `rviz:=true`, `map:=/path/map.yaml`, `params_file:=...`.

## How it fits together

```
/lidar_points ─► pointcloud_to_laserscan ─► /scan ─► costmaps, collision monitor, mapper
/lidar_points ─► x30_fastlio (adapter ─► FAST-LIO ─► localizer) ─► TF map -> odom
sim TF odom -> base_link ───────────────────────────────────────────────────────────┘
```

- `mode:=mapping`, `mapper:=fastlio` (default): `grid_mapper` builds the 2D map from `/scan` at FAST-LIO's pose,
  so the saved map is in the frame FAST-LIO localizes in. `mapper:=slam_toolbox` uses SLAM Toolbox instead; it diverged on
  this sparse scan under load, so prefer the default.
- `mode:=navigation`: `map_server` serves the saved map and FAST-LIO provides `map -> odom`.
  `localization:=amcl` uses AMCL instead (not tested).
- The map frame origin is the robot's start pose, so **start the simulator at the same spawn pose** you mapped from.

## Things to know

- The 2D scan keeps lidar points from -0.25 to 1.2 m around the body (`config/scan.yaml`). The lidar looks
  from -7 to +52 deg, so a thin band would miss most wall returns. Returns closer than 0.6 m are the robot's own legs.
- FAST-LIO does not recover once it diverges (for example after the gravity-free robot is driven into an obstacle).
  The localizer then keeps the last good `map -> odom` and logs an error: restart FAST-LIO, or reset with
  `/sim/reset_world`.
- Speed limits in `config/nav2_params.yaml` follow the sim: 0.4 m/s forward, 0.5 rad/s turning. Transform tolerances are
  0.5 s because the software-rendered sim stamps `map -> odom` about 0.2 s behind the clock.
- `nav2_params.yaml` still uses the default MPPI controller; it is slow but works.
- Map files for the AI pipeline: label them with `Map/Labeling.py` (pixel coordinates), and give the pixel size via
  `map_yaml:=...` to `x30_task_executor`.
