# x30_msgs

Message, service and action definitions shared by the X30 VLN framework and the
simulator. Interfaces only: no code, no nodes, no topics of its own.

## Build

`ament_cmake` with `rosidl_generate_interfaces`; depends on `builtin_interfaces`,
`std_msgs`, `geometry_msgs`, `sensor_msgs`. Built first in the workspace
(`colcon build --packages-up-to x30_msgs ...`). Python and C++ bindings are
generated automatically.

## Contents

| Interface | Kind | Meaning |
|---|---|---|
| `SemanticObject` | msg | One object instance in the map: id, label, confidence, position, size, caption, attributes, room, best view |
| `SemanticObjectArray` | msg | Header plus `SemanticObject[]` |
| `Detection3D` | msg | One segmented observation lifted to 3D: box, mask (RLE), centroid, extent, bearing, depth source, thermal stats, crop |
| `Detection3DArray` | msg | Detections from one camera frame, with the camera position |
| `SafetyStatus` | msg | Safety guard state: limiting, stopped, nearest obstacle, scale, reason |
| `Json` | srv | `string request` → `bool ok`, `string response` (JSON payloads) |
| `SetMode` | srv | Switch mode (`idle`, `teleop`, `velocity_follow`, `object_nav`, `goal_pose`, `explore`) |
| `Navigate` | action | Single entry point for a navigation task: mode, instruction, target label, goal, timeout |
| `Skill` | action | Run a named skill with JSON args; feedback has status and progress |

## Who uses what in the simulator

Only two are used by the simulator today:

- `SemanticObjectArray` is published on `/gt/objects` by the `ground_truth` node (latched).
- `Json` is the type of the `/sim/set_robot_pose` and `/sim/reset_world` services.

The rest (`Detection3D*`, `SafetyStatus`, `SetMode`, `Navigate`, `Skill`) are
for the higher-level framework, not for the sim.

## Building on it

1. Add the `.msg`, `.srv` or `.action` file under `msg/`, `srv/` or `action/`.
2. List it in `rosidl_generate_interfaces(...)` in `CMakeLists.txt`.
3. Add any new dependency package to both `CMakeLists.txt` and `package.xml`.
4. Rebuild with `sim-build`, and open a new shell so it is sourced.
