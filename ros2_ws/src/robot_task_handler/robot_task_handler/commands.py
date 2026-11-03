"""Validate the transport contract before publishing any part of a request."""

import json
import math
from dataclasses import dataclass
from typing import List, Union


@dataclass(frozen=True)
class Goal:
    goal_id: str
    x: float
    y: float


@dataclass(frozen=True)
class Teach:
    place_id: str
    description: str
    add: bool


@dataclass(frozen=True)
class Cancel:
    name: str = ''  # empty means cancel everything


@dataclass(frozen=True)
class ManagerError:
    message: str


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a non-empty string')
    return value


def _coordinate(value):
    if type(value) not in (int, float):
        raise ValueError('coordinates must be finite numbers')
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError('coordinate is outside float64 range') from exc
    if not math.isfinite(number):
        raise ValueError('coordinates must be finite numbers')
    return number


def _require_fields(task, fields, label):
    if set(task) != fields:
        raise ValueError(f'{label} requires exactly: {sorted(fields)}')


def _parse_reach(task):
    _require_fields(task, {'action', 'destination'}, 'reach')
    destination = task['destination']
    if not isinstance(destination, dict):
        raise ValueError('reach destination must be an object')
    _require_fields(destination, {'name', 'x', 'y'}, 'destination')
    return Goal(
        goal_id=_text(destination['name'], 'destination name'),
        x=_coordinate(destination['x']),
        y=_coordinate(destination['y']),
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


def _parse_standalone(command):
    """Cancel and error are interrupts, never part of a task list."""
    action = command.get('action')
    if action == 'cancel' and set(command) <= {'action', 'name'}:
        name = command.get('name', '')
        if not isinstance(name, str):
            raise ValueError('cancel name must be a string')
        return Cancel(name)
    if action == 'error':
        _require_fields(command, {'action', 'message'}, 'error')
        return ManagerError(_text(command['message'], 'error message'))
    raise ValueError('only cancel and error may be standalone objects')


_TASK_PARSERS = {'reach': _parse_reach, 'teach': _parse_teach}


def parse_command(raw: str) -> Union[List[Goal], List[Teach], Cancel, ManagerError]:
    """Validate all tasks atomically; never drop unsupported steps.

    The manager validates map membership. This transport layer checks shape
    and numbers, without maintaining a second copy of the map.
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
