"""Exercise actual DDS input/output with generated ROS messages.

Run in an isolated ROS_DOMAIN_ID, as in test_wsl.sh.
"""

import json
import time
from uuid import uuid4

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from interfaces.msg import GoalArray

from robot_task_handler.node import TaskHandler


def test_dispatch_over_ros_topics():
    rclpy.init()
    # Unique namespaces keep test topics separate from other nodes.
    namespace = '/handler_test_' + uuid4().hex
    handler = TaskHandler(namespace=namespace)
    peer = Node('test_peer', namespace=namespace)
    executor = SingleThreadedExecutor()
    executor.add_node(handler)
    executor.add_node(peer)
    arrays, cancels = [], []
    publisher = peer.create_publisher(String, 'manager/commands', 10)
    goals_sub = peer.create_subscription(GoalArray, 'robot/goals', arrays.append, 10)
    cancel_sub = peer.create_subscription(String, 'robot/cancel', cancels.append, 10)

    def until(predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
            if predicate():
                return
        assert predicate(), 'Timed out waiting for ROS discovery or delivery'

    try:
        until(lambda: publisher.get_subscription_count() == 1
              and handler.goals_publisher.get_subscription_count() == 1
              and handler.cancel_publisher.get_subscription_count() == 1)
        route = [
            {'action': 'reach', 'destination': {'name': 'A', 'x': 1, 'y': 2}},
            {'action': 'reach', 'destination': {'name': 'B', 'x': 3, 'y': 4}},
            {'action': 'reach', 'destination': {'name': 'A', 'x': 1, 'y': 2}},
        ]
        publisher.publish(String(data=json.dumps(route)))
        until(lambda: len(arrays) == 1)
        assert arrays[0].header.frame_id == 'map'
        assert arrays[0].header.stamp.sec > 0
        assert [(g.goalid, g.goal.pose.position.x, g.goal.pose.position.y)
                for g in arrays[0].goals] == [
            ('A', 1.0, 2.0), ('B', 3.0, 4.0), ('A', 1.0, 2.0)]
        for g in arrays[0].goals:
            assert g.goal.header == arrays[0].header
            assert g.goal.pose.position.z == 0.0
            assert (g.goal.pose.orientation.x, g.goal.pose.orientation.y,
                    g.goal.pose.orientation.z, g.goal.pose.orientation.w) == (0.0, 0.0, 0.0, 1.0)

        # Invalid sequences publish no partial goals and no cancellation.
        for tail in ({'action': 'wait', 'duration_seconds': 1},
                     {'action': 'teach'}, {'action': 'cancel'}):
            publisher.publish(String(data=json.dumps(route + [tail])))
        publisher.publish(String(data='{broken'))
        publisher.publish(String(data='{"action":"error","message":"Unknown location"}'))
        # Same input publisher orders Cancel after the rejected commands.
        publisher.publish(String(data='{"action":"cancel"}'))
        until(lambda: len(cancels) == 1)
        assert len(arrays) == 1
    finally:
        peer.destroy_subscription(goals_sub)
        peer.destroy_subscription(cancel_sub)
        executor.shutdown()
        handler.destroy_node()
        peer.destroy_node()
        rclpy.shutdown()
