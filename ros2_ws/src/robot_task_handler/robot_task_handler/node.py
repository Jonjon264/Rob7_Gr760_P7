"""Publish goals, teach/remove requests, or cancel signals; never execute tasks."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from interfaces.msg import CustomGoal, CustomTeach, GoalArray

from .commands import Cancel, ManagerError, Teach, parse_command


class TaskHandler(Node):
    def __init__(self, **kwargs):
        super().__init__('robot_task_handler', **kwargs)
        self.declare_parameter('command_topic', 'manager/commands')
        self.declare_parameter('goals_topic', 'robot/goals')
        self.declare_parameter('cancel_topic', 'robot/cancel')
        self.declare_parameter('teach_topic', 'robot/teach')
        self.declare_parameter('frame_id', 'map')
        self.goals_publisher = self.create_publisher(
            GoalArray, self.get_parameter('goals_topic').value, 10)
        # Carries the name of the task to cancel; an empty string cancels everything.
        self.cancel_publisher = self.create_publisher(
            String, self.get_parameter('cancel_topic').value, 10)
        self.teach_publisher = self.create_publisher(
            CustomTeach, self.get_parameter('teach_topic').value, 10)
        self.command_subscription = self.create_subscription(
            String, self.get_parameter('command_topic').value, self.on_command, 10)
        self.get_logger().info('Ready to dispatch Reach, Teach, and Cancel commands')

    def on_command(self, message):
        try:
            command = parse_command(message.data)
        except (ValueError, RecursionError) as exc:
            self.get_logger().error(f'Rejected manager command: {exc}')
            return

        if isinstance(command, ManagerError):
            self.get_logger().warning(f'Manager could not interpret request: {command.message}')
        elif isinstance(command, Cancel):
            self.publish_cancel(command)
        elif isinstance(command[0], Teach):
            self.publish_teach(command)
        else:
            self.publish_goals(command)

    def publish_cancel(self, cancel):
        self.cancel_publisher.publish(String(data=cancel.name))
        self.get_logger().info(f'Published cancel for: {cancel.name or "all tasks"}')

    def publish_teach(self, teaches):
        for teach in teaches:
            msg = CustomTeach()
            msg.action = CustomTeach.TEACH if teach.add else CustomTeach.REMOVE
            msg.place_id = teach.place_id
            msg.description = teach.description
            self.teach_publisher.publish(msg)
        self.get_logger().info(f'Published {len(teaches)} teach request(s)')

    def publish_goals(self, goals):
        array = GoalArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.header.frame_id = self.get_parameter('frame_id').value
        for g in goals:
            goal = CustomGoal(goalid=g.goal_id)
            goal.goal.header = array.header
            goal.goal.pose.position.x = g.x
            goal.goal.pose.position.y = g.y
            goal.goal.pose.orientation.w = 1.0
            array.goals.append(goal)
        self.goals_publisher.publish(array)
        self.get_logger().info(f'Published {len(array.goals)} ordered navigation goals')


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
