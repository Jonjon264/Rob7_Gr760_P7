"""Publish goal arrays or immediate cancel signals; never execute tasks."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, String
from interfaces.msg import CustomGoal, GoalArray

from .commands import Cancel, ManagerError, parse_command


class TaskHandler(Node):
    def __init__(self, **kwargs):
        super().__init__('robot_task_handler', **kwargs)
        self.declare_parameter('command_topic', 'manager/commands')
        self.declare_parameter('goals_topic', 'robot/goals')
        self.declare_parameter('cancel_topic', 'robot/cancel')
        self.declare_parameter('frame_id', 'map')
        self.goals_publisher = self.create_publisher(
            GoalArray, self.get_parameter('goals_topic').value, 10)
        self.cancel_publisher = self.create_publisher(
            Empty, self.get_parameter('cancel_topic').value, 10)
        self.command_subscription = self.create_subscription(
            String, self.get_parameter('command_topic').value, self.on_command, 10)
        self.get_logger().info('Ready to dispatch Reach lists and standalone Cancel commands')

    def on_command(self, message):
        try:
            command = parse_command(message.data)
        except (ValueError, RecursionError) as exc:
            self.get_logger().error(f'Rejected manager command: {exc}')
            return

        if isinstance(command, ManagerError):
            self.get_logger().warning(f'Manager could not interpret request: {command.message}')
        elif isinstance(command, Cancel):
            self.cancel_publisher.publish(Empty())
            self.get_logger().info('Published cancel-all signal')
        else:
            goals = GoalArray()
            goals.header.stamp = self.get_clock().now().to_msg()
            goals.header.frame_id = self.get_parameter('frame_id').value
            for g in command:
                goal = CustomGoal(goalid=g.goal_id)
                goal.goal.header = goals.header
                goal.goal.pose.position.x = g.x
                goal.goal.pose.position.y = g.y
                goal.goal.pose.orientation.w = 1.0
                goals.goals.append(goal)
            self.goals_publisher.publish(goals)
            self.get_logger().info(f'Published {len(goals.goals)} ordered navigation goals')


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TaskHandler()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
