"""Parse and validate the manager's JSON before anything is published.

parse_command() is all-or-nothing: if any task is invalid, ValueError is
raised and nothing is published. Map membership is checked upstream by the
Qwen agent; this layer only checks shape and number ranges.
"""

import json
import math
from dataclasses import dataclass
from typing import List, Union

MAX_WAIT_TIME = 32767  # CustomGoal.wait_time is an int16


# ---------------------------------------------------------------- parsed commands
@dataclass(frozen=True)
class Goal:
    """One stop. delivery_point waits for /robot/continue; otherwise wait_time seconds."""
    goal_id: str
    x: float
    y: float
    wait_time: int = 0
    delivery_point: bool = False


@dataclass(frozen=True)
class Teach:
    """Add (add=True) or remove a named place."""
    place_id: str
    description: str
    add: bool


@dataclass(frozen=True)
class Cancel:
    """Cancel one goal by name; an empty name cancels everything."""
    name: str = ''


@dataclass(frozen=True)
class Continue:
    """The person confirmed they received the delivery."""


@dataclass(frozen=True)
class ManagerError:
    """The manager could not interpret the request."""
    message: str


# ---------------------------------------------------------------- field checks
def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a non-empty string')
    return value


def _coordinate(value):
    # type() rather than isinstance() so True/False are not accepted as numbers.
    if type(value) not in (int, float):
        raise ValueError('coordinates must be finite numbers')
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError('coordinate is outside float64 range') from exc
    if not math.isfinite(number):
        raise ValueError('coordinates must be finite numbers')
    return number


def _require_fields(obj, fields, label):
    """The object must contain exactly these keys, no more, no fewer."""
    if set(obj) != fields:
        raise ValueError(f'{label} requires exactly: {sorted(fields)}')


# ---------------------------------------------------------------- task parsers
def _parse_reach(task):
    _require_fields(task, {'action', 'destination', 'wait_time', 'delivery_point'}, 'reach')
    if type(task['delivery_point']) is not bool:
        raise ValueError('delivery_point must be true or false')
    wait_time = task['wait_time']
    if type(wait_time) is not int or not 0 <= wait_time <= MAX_WAIT_TIME:
        raise ValueError(f'wait_time must be a whole number of seconds from 0 to {MAX_WAIT_TIME}')

    destination = task['destination']
    if not isinstance(destination, dict):
        raise ValueError('reach destination must be an object')
    _require_fields(destination, {'name', 'x', 'y'}, 'destination')
    return Goal(
        goal_id=_text(destination['name'], 'destination name'),
        x=_coordinate(destination['x']),
        y=_coordinate(destination['y']),
        wait_time=wait_time,
        delivery_point=task['delivery_point'],
    )


def _parse_teach(task):
    _require_fields(task, {'action', 'name', 'descriptor', 'add'}, 'teach')
    if not isinstance(task['add'], bool):
        raise ValueError('teach add must be true or false')
    return Teach(
        place_id=_text(task['name'], 'teach name'),
        description=_text(task['descriptor'], 'teach descriptor'),
        add=task['add'],
    )


_TASK_PARSERS = {'reach': _parse_reach, 'teach': _parse_teach}


def _parse_standalone(command):
    """Cancel, continue and error are interrupts, never part of a task list."""
    action = command.get('action')
    if action == 'continue':
        _require_fields(command, {'action'}, 'continue')
        return Continue()
    if action == 'cancel' and set(command) <= {'action', 'name'}:
        name = command.get('name', '')
        if not isinstance(name, str):
            raise ValueError('cancel name must be a string')
        return Cancel(name)
    if action == 'error':
        _require_fields(command, {'action', 'message'}, 'error')
        return ManagerError(_text(command['message'], 'error message'))
    raise ValueError('only cancel, continue and error may be standalone objects')


# ---------------------------------------------------------------- entry point
def parse_command(raw: str) -> Union[List[Goal], List[Teach], Cancel, Continue, ManagerError]:
    """Parse the JSON string from manager/commands.

    A dict is a standalone command; a non-empty list is a task list of all
    reach or all teach tasks (mixing is not supported yet).
    """
    command = json.loads(raw)
    if isinstance(command, dict):
        return _parse_standalone(command)
    if not isinstance(command, list) or not command:
        raise ValueError('expected a non-empty list of tasks')

    tasks = []
    for index, task in enumerate(command):
        if not isinstance(task, dict) or task.get('action') not in _TASK_PARSERS:
            raise ValueError(f'task {index}: only reach and teach are supported in task lists')
        try:
            tasks.append(_TASK_PARSERS[task['action']](task))
        except ValueError as exc:
            raise ValueError(f'task {index}: {exc}') from exc

    if len({type(t) for t in tasks}) > 1:
        raise ValueError('mixing reach and teach in one request is not supported yet')
    return tasks
