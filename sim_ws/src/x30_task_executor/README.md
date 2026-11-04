# x30_task_executor

Runs the AI task pipeline on the simulated X30. It is the consumer of the topics that
`robot_task_handler` publishes, and drives Nav2.

```
voice / text ──► qwen_voice_manager ──manager/commands──► robot_task_handler ──┬─ robot/goals  (interfaces/GoalArray)
 (manager/text)        (remote Qwen API)                                       ├─ robot/cancel (std_msgs/String)
                                                                               └─ robot/teach  (interfaces/CustomTeach)
                                                                                        │
                                                           x30_task_executor ◄──────────┘
                                                                  │ NavigateToPose action
                                                                  ▼
                                                          Nav2 (x30_navigation)
```

| Input | Behaviour |
|---|---|
| `robot/goals` | A new request replaces whatever is queued, and cancels the active goal. Goals run one after another with `navigate_to_pose`; a failed leg drops the rest of the route. |
| `robot/cancel` | Empty name cancels the active goal and the queue. A name cancels the queued or active goal with that id. |
| `robot/teach` | Teach adds the robot's current `map -> base_link` position to `map_file` under the given name and description. Remove deletes the place. The voice manager re-reads the file on every request. |

Progress is published as text on `robot/status`.

Goals only move the robot once Nav2 is running with a map and localization
(see [x30_navigation](../x30_navigation/README.md)).

Places in `map.json` are **image pixels**, as clicked in `Map/Labeling.py`. Pass the map yaml they were labelled on
(`map_yaml:=/x30/configs/maps/<world>/map.yaml`) and the executor converts pixels to metres for Nav2, and stores taught
places back as pixels. Without `map_yaml`, coordinates are taken as metres. The default
`qwen_voice_manager/config/map.json` holds factory coordinates: give the launch your own labelled file with `map_file:=...`.

## Run

```bash
ros2 launch x30_task_executor ai_tasks.launch.py map_file:=/path/to/places.json \
    map_yaml:=/x30/configs/maps/aws_hospital/map.yaml
ros2 topic pub --once /manager/text std_msgs/msg/String "{data: 'go to the charging station'}"
```

`speech_enabled:=true` turns on the wake-word microphone path. The image carries the speech
dependencies; to give the container the host microphone start the sim with `SIM_AUDIO=true bash docker/sim/gui.sh`
(see `docker/sim/docker-compose.audio.yaml`). `QWEN_API_KEY` overrides the key built into the Qwen agent.

## Test

```bash
python3 -m pytest -q /ws/src/x30_task_executor/test
```

The ROS test runs the executor against a fake Nav2 action server, so no map is needed.
