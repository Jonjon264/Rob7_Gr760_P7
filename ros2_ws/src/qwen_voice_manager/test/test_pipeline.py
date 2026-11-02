import json
from queue import Queue
import threading
import time
from uuid import uuid4

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Empty, String
from interfaces.msg import GoalArray
from robot_task_handler.node import TaskHandler
from qwen_voice_manager.node import VoiceManager


ROUTE = [{'action': 'reach', 'destination': {'name': 'Charging Station', 'x': 231, 'y': 113}}]


class Agent:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()

    def ask(self, text):
        self.calls.append(text)
        if text == 'slow request':
            self.started.set()
            assert self.release.wait(5)
        if text == 'endpoint failure':
            raise ConnectionError('simulated endpoint failure')
        return ROUTE


@pytest.fixture
def pipeline():
    rclpy.init()
    namespace = '/voice_test_' + uuid4().hex
    agent = Agent()
    manager = VoiceManager(agent=agent, namespace=namespace,
                           parameter_overrides=[Parameter('speech_enabled', value=False)])
    handler = TaskHandler(namespace=namespace)
    peer = Node('test_peer', namespace=namespace)
    executor = SingleThreadedExecutor()
    for node in (manager, handler, peer):
        executor.add_node(node)
    goals, cancels, results, transcripts = [], [], [], []
    publisher = peer.create_publisher(String, 'manager/text', 10)
    subscriptions = [
        peer.create_subscription(GoalArray, 'robot/goals', goals.append, 10),
        peer.create_subscription(Empty, 'robot/cancel', cancels.append, 10),
        peer.create_subscription(String, 'manager/commands', lambda msg: results.append(json.loads(msg.data)), 10),
        peer.create_subscription(String, 'manager/transcripts', lambda msg: transcripts.append(msg.data), 10),
    ]

    def until(predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.02)
            if predicate():
                return
        assert predicate(), 'Timed out waiting for voice-manager pipeline'

    until(lambda: publisher.get_subscription_count() == 1
          and manager.command_publisher.get_subscription_count() == 2
          and handler.goals_publisher.get_subscription_count() == 1
          and handler.cancel_publisher.get_subscription_count() == 1
          and manager.transcript_publisher.get_subscription_count() == 1)
    try:
        yield manager, agent, publisher, goals, cancels, results, transcripts, until
    finally:
        agent.release.set()
        executor.shutdown()
        manager.destroy_node()
        handler.destroy_node()
        for sub in subscriptions:
            peer.destroy_subscription(sub)
        peer.destroy_node()
        rclpy.shutdown()


def test_text_to_qwen_to_handler_and_error_recovery(pipeline):
    manager, agent, publisher, goals, cancels, results, transcripts, until = pipeline
    publisher.publish(String(data='go recharge'))
    until(lambda: len(goals) == 1 and len(transcripts) == 1)
    assert agent.calls == ['go recharge']
    assert goals[0].goals[0].goalid == 'Charging Station'
    assert goals[0].goals[0].goal.pose.position.x == 231.0
    assert goals[0].goals[0].goal.pose.position.y == 113.0
    assert transcripts == ['go recharge']
    publisher.publish(String(data='endpoint failure'))
    until(lambda: len(results) == 2)
    assert results[-1]['action'] == 'error'
    assert len(goals) == 1
    publisher.publish(String(data='go recharge again'))
    until(lambda: len(goals) == 2)


def test_stop_bypasses_busy_model_and_discards_old_requests(pipeline):
    manager, agent, publisher, goals, cancels, results, transcripts, until = pipeline
    publisher.publish(String(data='slow request'))
    until(agent.started.is_set)
    publisher.publish(String(data='old queued request'))
    publisher.publish(String(data='Stop now!'))
    until(lambda: len(cancels) == 1)
    assert not goals
    assert 'Stop now!' not in agent.calls
    agent.release.set()
    publisher.publish(String(data='fresh request'))
    until(lambda: len(goals) == 1)
    assert agent.calls == ['slow request', 'fresh request']
    assert len(results) == 2  # Cancel, then fresh route; no stale route.


def test_speech_callback_uses_shared_recorder_factory():
    rclpy.init()
    observed = {}
    utterances = Queue()
    utterances.put('go recharge')

    class Recorder:
        def text(self, callback):
            text = utterances.get()
            if text is not None:
                callback(text)

        def shutdown(self):
            observed['shutdown'] = True
            utterances.put(None)

    def factory(**options):
        observed.update(options)
        return Recorder()

    agent = Agent()
    manager = VoiceManager(agent=agent, recorder_factory=factory,
                           namespace='/speech_test_' + uuid4().hex)
    try:
        deadline = time.monotonic() + 5
        while not agent.calls and time.monotonic() < deadline:
            rclpy.spin_once(manager, timeout_sec=0.02)
        assert agent.calls == ['go recharge']
        assert observed['model'] == 'base.en'
        assert observed['device'] == 'cpu'
        assert observed['wake_words'] == 'bumblebee'
    finally:
        manager.destroy_node()
        rclpy.shutdown()
    assert observed['shutdown']
