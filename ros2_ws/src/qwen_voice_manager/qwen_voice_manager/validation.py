"""Parse and validate the JSON a Qwen model returns. Pure functions, no ROS or network.

Valid output is either
  a task list : [{"action": "reach", ...}, {"action": "teach", ...}, ...]
  or one standalone object: {"action": "cancel", "name": ...}
                            | {"action": "continue"} | {"action": "error", "message": ...}
Field-by-field rules for reach/teach are in config/rules.txt and mirrored here.
"""

import json
import re

ACTIONS = {"reach", "teach", "cancel", "continue"}
TASK_ACTIONS = {"reach", "teach"}  # only these may appear inside a task list
MAX_WAIT_TIME = 32767              # CustomGoal.wait_time is an int16


def parse_json(text):
    """Parse the model output, dropping any <think>...</think> block first."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return json.loads(text)


def split_reply(output):
    """Separate the human-facing "reply" from the commands.

    Returns (commands without "reply" fields, all replies joined into one string).
    """
    items = output if isinstance(output, list) else [output]
    commands, replies = [], []
    for item in items:
        if isinstance(item, dict) and "reply" in item:
            item = dict(item)
            reply = item.pop("reply")
            if not isinstance(reply, str):
                raise ValueError("reply must be a string")
            if reply.strip():
                replies.append(reply.strip())
        commands.append(item)
    return (commands if isinstance(output, list) else commands[0]), " ".join(replies)


# ---------------------------------------------------------------- validation
def validate(cmd, map_data):
    """Return cmd if it is a valid task list or standalone object, else raise ValueError."""
    if isinstance(cmd, list):
        if not cmd:
            raise ValueError("task list must not be empty")
        for task in cmd:
            validate_task(task, map_data)
        return cmd
    if not isinstance(cmd, dict):
        raise ValueError("output must be a task list or a standalone cancel/continue/error object")

    action = cmd.get("action")
    if action == "error":
        if set(cmd) != {"action", "message"} or not isinstance(cmd["message"], str) or not cmd["message"].strip():
            raise ValueError("error requires only action and a non-empty message")
    elif action == "continue":
        if set(cmd) != {"action"}:
            raise ValueError("continue requires only action")
    elif action == "cancel":
        if set(cmd) != {"action", "name"} or not isinstance(cmd["name"], str):
            raise ValueError("cancel requires only action and name")
        if cmd["name"] not in {"teach"} | {p["name"] for p in map_data}:
            raise ValueError(f"cancel name is not a known task: {cmd['name']}")
    else:
        raise ValueError("only cancel, continue and error may be standalone objects; use a list for tasks")
    return cmd


def validate_task(cmd, map_data):
    """Check one entry of a task list (reach or teach)."""
    if not isinstance(cmd, dict):
        raise ValueError("each task must be a JSON object")
    action = cmd.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    if action not in TASK_ACTIONS:
        raise ValueError(f"{action} must be a standalone object outside the task list")

    fields = {
        "reach": {"action", "destination", "wait_time", "delivery_point"},
        "teach": {"action", "name", "descriptor", "add"},
    }[action]
    if set(cmd) != fields:
        raise ValueError(f"{action} requires exactly these fields: {sorted(fields)}")

    if action == "reach":
        _validate_reach(cmd, map_data)
    else:
        _validate_teach(cmd, map_data)
    return cmd


def _validate_reach(cmd, map_data):
    # The destination must be an exact copy of a map entry (name, x, y).
    dest = cmd["destination"]
    known = [{"name": p["name"], "x": p["x"], "y": p["y"]} for p in map_data]
    if (
        not isinstance(dest, dict)
        or set(dest) != {"name", "x", "y"}
        or type(dest["x"]) not in (int, float)
        or type(dest["y"]) not in (int, float)
        or dest not in known
    ):
        raise ValueError(f"destination is not on map: {dest}")
    if type(cmd["delivery_point"]) is not bool:
        raise ValueError("delivery_point must be true or false")
    if type(cmd["wait_time"]) is not int or not 0 <= cmd["wait_time"] <= MAX_WAIT_TIME:
        raise ValueError(f"wait_time must be a whole number of seconds from 0 to {MAX_WAIT_TIME}")
    if cmd["delivery_point"] and cmd["wait_time"] != 0:
        raise ValueError("wait_time must be 0 for a delivery point")  # it waits for "continue" instead


def _validate_teach(cmd, map_data):
    if not all(isinstance(cmd[k], str) and cmd[k].strip() for k in ("name", "descriptor")):
        raise ValueError("teach name and descriptor must be non-empty strings")
    if not isinstance(cmd["add"], bool):
        raise ValueError("teach add must be true or false")
    # Removing a spot: name and descriptor must match an existing map entry.
    entry = {"name": cmd["name"], "descriptor": cmd["descriptor"]}
    if not cmd["add"] and entry not in [{"name": p["name"], "descriptor": p["descriptor"]} for p in map_data]:
        raise ValueError(f"teach removal is not on map: {cmd['name']}")
