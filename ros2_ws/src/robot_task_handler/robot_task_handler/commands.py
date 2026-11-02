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
class Cancel:
    pass


@dataclass(frozen=True)
class ManagerError:
    message: str


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


def parse_command(raw: str) -> Union[List[Goal], Cancel, ManagerError]:
    """Validate all tasks atomically; never drop unsupported steps.

    The manager validates map membership. This transport layer checks shape
    and numbers, without maintaining a second copy of the map.
    """
    command = json.loads(raw)
    if isinstance(command, dict):
        if command == {'action': 'cancel'}:
            return Cancel()
        if (
            set(command) == {'action', 'message'}
            and command['action'] == 'error'
            and isinstance(command['message'], str)
            and command['message'].strip()
        ):
            return ManagerError(command['message'])
        raise ValueError('only cancel and error may be standalone objects')
    if not isinstance(command, list) or not command:
        raise ValueError('expected a non-empty list of Reach tasks')

    goals = []
    for index, task in enumerate(command):
        if not isinstance(task, dict) or task.get('action') != 'reach':
            raise ValueError(f'task {index}: only Reach is supported in task lists')
        if set(task) != {'action', 'destination'}:
            raise ValueError(f'task {index}: Reach requires action and destination only')
        destination = task['destination']
        if not isinstance(destination, dict) or set(destination) != {'name', 'x', 'y'}:
            raise ValueError(f'task {index}: destination requires name, x, and y only')
        if not isinstance(destination['name'], str) or not destination['name'].strip():
            raise ValueError(f'task {index}: destination name must be non-empty')
        goals.append(Goal(
            goal_id=destination['name'],
            x=_coordinate(destination['x']),
            y=_coordinate(destination['y']),
        ))
    return goals
