# X30 simulation

This container uses ROS 2 Jazzy and Gazebo Harmonic. Its workspace is separate
from the Humble workspace in `ros2_ws`.

Package documentation: [sim_ws/README.md](../../sim_ws/README.md) (overview and topic
contract), [x30_sim](../../sim_ws/src/x30_sim/README.md),
[x30_msgs](../../sim_ws/src/x30_msgs/README.md),
[x30_worlds](../../sim_ws/src/x30_worlds/README.md).

Included source:

- `sim_ws/src/x30_sim`: simulator, robot xacro, built-in worlds, existing tests.
- `sim_ws/src/x30_msgs`: custom interfaces used by the simulator.
- `sim_ws/src/x30_worlds`: the migrated AWS hospital and its model assets.
- `configs/sim/robot_sim.yaml`: robot geometry, sensors, topics, and limits.
- `configs/sim/worlds.yaml`: world registry and hospital spawn pose.
- `docker/sim/patches/unitree_guide_x30.patch`: original controller fixes.

The Dockerfile builds `quadruped_ros2_control` at commit
`5434c5810d1a7fe223bcfd04550e9d3bfdd4b458`, applies the controller patch and
documented IMU mounting correction, then builds the simulator packages.
The original setup's unused navigation clone, unrelated datasets, logs, and results
are excluded.

For the hospital, Gazebo window, and original on-screen joystick, run from
the repository root:

```bash
python3 docker/sim/prepare_hospital.py
docker compose -f docker/sim/docker-compose.yaml build sim
bash docker/sim/gui.sh
```

The preparation script restores 69 referenced AWS/Fuel models, records pinned
versions and archive checksums in `hospital-assets.lock.json`, and keeps model
binaries out of Git. It resumes from completed models on subsequent runs.

`gui.sh` prepares display authorization, refreshes the installed workspace in
its existing volumes, and starts one Docker-managed simulator with
`world:=aws_hospital gui:=true joystick:=true`. View its logs or stop it with:

```bash
bash docker/sim/gui.sh logs -f sim
bash docker/sim/gui.sh down
```

Do not launch another simulator with `docker exec` while this service runs.
A launch lock rejects a second instance in the same container to avoid
conflicting clocks, sensor streams, and world files. The window uses software
rendering; `SIM_WORLD` and `SIM_LOCOMOTION` select the world and motion mode.
The GUI overlay shares host IPC for Mesa's X11 display buffers. Its camera
starts behind the robot's spawn, below the ceiling and looking at the robot.
The Gazebo window waits for the spawned robot in the server's scene so imported scenes
include its visuals when the client connects. The hospital can take a little
longer to appear with software rendering.

The joystick has a movement pad, a turning bar, and keyboard controls:

- W/S: forward/back; A/D: strafe; Q/E: turn.
- Space: stop. Releasing an input or moving focus out of the joystick stops it.
- Limits: 0.4 m/s forward, 0.3 m/s sideways, 0.5 rad/s turning.

Click the joystick window before using its keys. It sends to `/cmd_vel` in
the simulator's ROS domain. To hide it, start with `SIM_JOYSTICK=false`.
To use the small test arena instead of the hospital:

```bash
SIM_WORLD=default_arena bash docker/sim/gui.sh
```

For a headless container with a manual foreground launch instead:

```bash
docker compose -f docker/sim/docker-compose.yaml build sim
docker compose -f docker/sim/docker-compose.yaml up -d sim
docker compose -f docker/sim/docker-compose.yaml exec sim bash
```

Inside that shell, start the built-in arena:

```bash
ros2 launch x30_sim sim.launch.py world:=default_arena locomotion:=kinematic
```

The launch runs in the foreground. Ctrl+C stops it. To stop the container:

```bash
docker compose -f docker/sim/docker-compose.yaml down
```

Source is mounted at `/ws/src`, the repository at `/x30`, and build/install/log
outputs are stored in dedicated Compose volumes. After editing simulator source:

```bash
docker compose -f docker/sim/docker-compose.yaml exec sim sim-build
```

Open a new shell after rebuilding so it sources the updated installation.
After rebuilding the Docker image, run `sim-build` in the recreated container
to refresh any existing workspace volumes. `down` preserves these volumes.

Run the existing tests in a temporary container:

```bash
docker compose -f docker/sim/docker-compose.yaml run --rm sim \
  bash -lc 'python3 -m pytest -q /ws/src/x30_sim/test'
```

The base Compose file uses headless software rendering, private Compose
networking, and ROS domain 10. `SIM_ROS_DOMAIN_ID`, `SIM_BUILD_JOBS`, and `SIM_RENDER_THREADS`
can be set in the shell before running Compose. On Linux, set `HOST_UID` and
`HOST_GID` to `id -u` and `id -g` if your account differs from 1000.

Connecting to Humble/FAST-LIO, importing further worlds, and configuring
GPU acceleration are separate integration steps. FAST-LIO's existing Livox custom
message input does not directly match the simulated `PointCloud2` output.

Gazebo may print `gz_frame_id` schema warnings and missing-material warnings
for the simplified robot meshes. These do not prevent sensor publishing;
the published LiDAR, IMU, and RGB frame IDs have been checked.

The LiDAR merger buffers staggered sensor messages by timestamp. It publishes
a partial scan only when matching inputs are still missing after 0.25 seconds
of simulation time. A repeated partial-scan warning warrants checking sensor
delivery and processing load. In the built-in arena, a 15-second check measured
10 Hz merged output with 79,872 points and no partial-scan warnings.
