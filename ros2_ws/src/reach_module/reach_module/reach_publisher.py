import rclpy
from rclpy.node import Node
from collections import deque
from actionlib_msgs.msg import GoalStatus
from interfaces.msg import GoalArray
from move_base_msgs.msg import MoveBaseActionGoal, MoveBaseActionResult

# Statuses that mean "move_base is done with this goal"
TERMINAL = {
    GoalStatus.PREEMPTED,   # 2
    GoalStatus.SUCCEEDED,   # 3
    GoalStatus.ABORTED,     # 4
    GoalStatus.REJECTED,    # 5
    GoalStatus.RECALLED,    # 8
}


class ReachPublisher(Node):
    """Forward GoalArray goals to move_base one at a time."""

    def __init__(self) -> None:
        super().__init__('reach_publisher')

        self.goal_publisher = self.create_publisher(
            MoveBaseActionGoal, '/move_base/goal', 10)
        self.create_subscription(
            GoalArray, '/goal_array', self.goal_callback, 10)
        self.create_subscription(
            MoveBaseActionResult, '/move_base/result', self.result_callback, 10)

        self.queue = deque()
        self.current_id = None   # id of the goal currently being executed
        self.counter = 0

    def goal_callback(self, message: GoalArray) -> None:
        if not message.goals:
            self.get_logger().warn('Received empty GoalArray, ignoring')
            return

        # A new array replaces whatever was pending
        self.queue = deque(message.goals)
        self.get_logger().info(f'Queued {len(self.queue)} goals')
        self.send_next()

    def send_next(self) -> None:
        if not self.queue:
            self.current_id = None
            self.get_logger().info('All goals completed')
            return

        goal = self.queue.popleft()

        msg = MoveBaseActionGoal()
        msg.header.stamp = self.get_clock().now().to_msg()
        self.counter += 1
        self.current_id = f'{self.get_name()}-{self.counter}'
        msg.goal_id.id = self.current_id
        msg.header.frame_id = "map"
        # msg.goal_id.stamp = msg.header.stamp

        # msg.goal.target_pose.header = goal.header
        msg.goal.target_pose.header.frame_id = "map"
        msg.goal.target_pose.pose.position.x = goal.goal.pose.position.x
        msg.goal.target_pose.pose.position.y = goal.goal.pose.position.y

        self.goal_publisher.publish(msg)
        self.get_logger().info(
            f'Sent goal {self.current_id} ({len(self.queue)} remaining)')

    def result_callback(self, message: MoveBaseActionResult) -> None:
        # Ignore results for goals we didn't send
        if message.status.goal_id.id != self.current_id:
            return

        status = message.status.status
        if status not in TERMINAL:
            return

        if status == GoalStatus.SUCCEEDED:
            self.get_logger().info(f'Goal {self.current_id} reached')
            self.send_next()
        else:
            self.get_logger().error(
                f'Goal {self.current_id} ended with status {status}: '
                f'{message.status.text}. Aborting remaining goals.')
            self.queue.clear()
            self.current_id = None


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ReachPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()