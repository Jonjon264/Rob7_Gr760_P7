import json

import pytest

from robot_task_handler.commands import Cancel, Goal, ManagerError, parse_command


def reach(name='Robot Cage', x=334, y=132):
    return {'action': 'reach', 'destination': {'name': name, 'x': x, 'y': y}}


def test_preserve_order_and_repeated_visits():
    tasks = [reach(), reach('Charging Station', 231, 113), reach()]
    assert parse_command(json.dumps(tasks)) == [
        Goal('Robot Cage', 334.0, 132.0),
        Goal('Charging Station', 231.0, 113.0),
        Goal('Robot Cage', 334.0, 132.0),
    ]


def test_standalone_control_messages():
    assert isinstance(parse_command('{"action":"cancel"}'), Cancel)
    assert parse_command('{"action":"error","message":"Unknown location"}') == ManagerError('Unknown location')


@pytest.mark.parametrize('command', [
    [], None, 1, reach(),
    {'action': 'cancel', 'extra': True},
    {'action': 'error', 'message': ''},
    [reach(), {'action': 'wait', 'duration_seconds': 2}],
    [reach(), {'action': 'teach'}],
    [reach(), {'action': 'cancel'}],
    [reach(), None],
    [reach(x=True)], [reach(x='334')], [reach(x=float('nan'))],
    [reach(y=float('inf'))], [reach(x=10 ** 400)], [reach(name='')],
    [{'action': 'reach', 'destinations': [reach()['destination']]}],
    [{**reach(), 'extra': 1}],
])
def test_reject_entire_invalid_sequence(command):
    with pytest.raises(ValueError):
        parse_command(json.dumps(command))


def test_reject_malformed_json():
    with pytest.raises(ValueError):
        parse_command('[invalid')
