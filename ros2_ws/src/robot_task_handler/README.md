# robot_task_handler

Turns the manager's JSON into ROS messages. It only publishes; it never moves the robot.
Invalid JSON publishes nothing (all-or-nothing).

## Input
`manager/commands` (String, JSON)

| JSON | Meaning |
|---|---|
| `[{"action":"reach","destination":{"name","x","y"},"wait_time":5,"delivery_point":false}, ...]` | Ordered stops. `delivery_point:true` waits for `/robot/continue` (`wait_time` 0); otherwise pauses `wait_time` s (0–32767). |
| `[{"action":"teach","name","descriptor","add":true}]` | Add/remove a place. Reach and teach can't be mixed. |
| `{"action":"cancel","name":"<goal>"}` | Cancel one goal (empty name = all). |
| `{"action":"continue"}` | Person confirmed receipt. |
| `{"action":"error","message":"..."}` | Logged only. |

## Output
| Topic | Type |
|---|---|
| `robot/goals` | `interfaces/GoalArray` (`CustomGoal`: goalid, wait_time, delivery_point, pose) |
| `robot/teach` | `interfaces/CustomTeach` |
| `robot/cancel` | `std_msgs/String` |
| `robot/continue` | `std_msgs/Bool` (always `true`) |

## Parameters
`command_topic`, `goals_topic`, `cancel_topic`, `teach_topic`, `continue_topic` (topic names above), `frame_id` (`map`).

## Test
`pytest test/test_commands.py` (no ROS needed); `test_transport.py` needs a sourced ROS workspace.
