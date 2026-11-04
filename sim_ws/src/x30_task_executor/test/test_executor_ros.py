"""Run the executor against a fake Nav2 navigate_to_pose server over real ROS topics/actions."""

import json
import time
from uuid import uuid4

import pytest
import rclpy
from interfaces.msg import CustomGoal, CustomTeach, GoalArray
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer, CancelResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from x30_task_executor.node import TaskExecutor


@pytest.fixture
def rig(tmp_path):
    rclpy.init()
    namespace = '/exec_test_' + uuid4().hex
    map_file = tmp_path / 'map.json'
    map_file.write_text('[]')
    executor_node = TaskExecutor(
        namespace=namespace, parameter_overrides=[rclpy.parameter.Parameter(
            'map_file', rclpy.Parameter.Type.STRING, str(map_file))])
    peer = Node('peer', namespace=namespace)
    visited, state = [], {'hold': False}

    def execute(handle):
        visited.append((handle.request.pose.pose.position.x, handle.request.pose.pose.position.y))
        while state['hold'] and not handle.is_cancel_requested:
            time.sleep(0.02)
        result = NavigateToPose.Result()
        if handle.is_cancel_requested:
            handle.canceled()
        else:
            handle.succeed()
        return result

    ActionServer(peer, NavigateToPose, 'navigate_to_pose', execute,
                 cancel_callback=lambda _: CancelResponse.ACCEPT)
    goals = peer.create_publisher(GoalArray, 'robot/goals', 10)
    cancel = peer.create_publisher(String, 'robot/cancel', 10)
    teach = peer.create_publisher(CustomTeach, 'robot/teach', 10)
    statuses = []
    peer.create_subscription(String, 'robot/status', lambda m: statuses.append(m.data), 10)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(executor_node)
    executor.add_node(peer)

    def until(predicate, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
            if predicate():
                return
        assert predicate(), f'timed out; statuses={statuses}'

    until(lambda: goals.get_subscription_count() == 1 and cancel.get_subscription_count() == 1)
    yield dict(goals=goals, cancel=cancel, teach=teach, visited=visited, state=state,
               statuses=statuses, until=until, map_file=map_file)
    executor.shutdown()
    executor_node.destroy_node()
    peer.destroy_node()
    rclpy.shutdown()


def goal_array(*points):
    array = GoalArray()
    for name, x, y in points:
        goal = CustomGoal(goalid=name)
        goal.goal.pose.position.x = float(x)
        goal.goal.pose.position.y = float(y)
        goal.goal.pose.orientation.w = 1.0
        array.goals.append(goal)
    return array


def test_goals_are_visited_in_order(rig):
    rig['goals'].publish(goal_array(('A', 1, 2), ('B', 3, 4)))
    rig['until'](lambda: 'Reached B' in rig['statuses'])
    assert rig['visited'] == [(1.0, 2.0), (3.0, 4.0)]


def test_cancel_all_stops_active_goal_and_drops_rest(rig):
    rig['state']['hold'] = True
    rig['goals'].publish(goal_array(('A', 1, 2), ('B', 3, 4)))
    rig['until'](lambda: len(rig['visited']) == 1)
    rig['cancel'].publish(String(data=''))
    rig['until'](lambda: 'Cancelled A' in rig['statuses'])
    time.sleep(0.5)
    assert rig['visited'] == [(1.0, 2.0)]


def test_teach_without_tf_reports_failure_and_remove_works(rig):
    rig['map_file'].write_text(json.dumps([{'x': 1, 'y': 2, 'name': 'Dock', 'descriptor': 'd'}]))
    message = CustomTeach(action=CustomTeach.TEACH, place_id='Lab', description='lab')
    rig['teach'].publish(message)
    rig['until'](lambda: any(s.startswith('Teach failed') for s in rig['statuses']))
    rig['teach'].publish(CustomTeach(action=CustomTeach.REMOVE, place_id='Dock', description='d'))
    rig['until'](lambda: 'Removed 1 place(s) named Dock' in rig['statuses'])
    assert json.loads(rig['map_file'].read_text()) == []
