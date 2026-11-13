"""Translate manager JSON into ROS messages. Publishes only; never executes tasks.

  manager/commands (String, JSON) -> robot/goals     (GoalArray)   reach tasks
                                  -> robot/teach     (CustomTeach) teach tasks
                                  -> robot/cancel    (String)      cancel
                                  -> robot/continue  (Bool, True)  delivery confirmed
Topic names and frame_id are ROS parameters (see README.md).
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from interfaces.msg import CustomGoal, CustomTeach, GoalArray

from .commands import Cancel, Continue, ManagerError, Teach, parse_command


class TaskHandler(Node):
    def __init__(self, **kwargs):
        super().__init__('robot_task_handler', **kwargs)
        self.declare_parameter('command_topic', 'manager/commands')
        self.declare_parameter('goals_topic', 'robot/goals')
        self.declare_parameter('cancel_topic', 'robot/cancel')
        self.declare_parameter('teach_topic', 'robot/teach')
        self.declare_parameter('continue_topic', 'robot/continue')
        self.declare_parameter('frame_id', 'map')

        def topic(name):
            return self.get_parameter(name).value

        self.goals_publisher = self.create_publisher(GoalArray, topic('goals_topic'), 10)
        # Carries the name of the goal to cancel; an empty string cancels everything.
        self.cancel_publisher = self.create_publisher(String, topic('cancel_topic'), 10)
        self.continue_publisher = self.create_publisher(Bool, topic('continue_topic'), 10)
        self.teach_publisher = self.create_publisher(CustomTeach, topic('teach_topic'), 10)
        self.command_subscription = self.create_subscription(
            String, topic('command_topic'), self.on_command, 10)
        self.get_logger().info('Ready to dispatch Reach, Teach, Cancel and Continue commands')

    def on_command(self, message):
        """Validate the whole message first; invalid input publishes nothing."""
        try:
            command = parse_command(message.data)
        except (ValueError, RecursionError) as exc:
            self.get_logger().error(f'Rejected manager command: {exc}')
            return

        if isinstance(command, ManagerError):
            self.get_logger().warning(f'Manager could not interpret request: {command.message}')
        elif isinstance(command, Cancel):
            self.publish_cancel(command)
        elif isinstance(command, Continue):
            self.continue_publisher.publish(Bool(data=True))
            self.get_logger().info('Published continue')
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
        """Publish all goals as one ordered GoalArray (the reach node queues them)."""
        array = GoalArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.header.frame_id = self.get_parameter('frame_id').value
        for g in goals:
            goal = CustomGoal(goalid=g.goal_id, wait_time=g.wait_time,
                              delivery_point=g.delivery_point)
            goal.goal.header = array.header
            goal.goal.pose.position.x = g.x
            goal.goal.pose.position.y = g.y
            goal.goal.pose.orientation.w = 1.0  # no heading given: identity orientation
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
