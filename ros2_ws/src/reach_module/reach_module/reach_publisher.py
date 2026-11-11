import rclpy
import std_msgs.msg
from rclpy.node import Node
from collections import deque
from actionlib_msgs.msg import GoalStatus, GoalID
from interfaces.msg import GoalArray
from move_base_msgs.msg import MoveBaseActionGoal, MoveBaseActionResult
import socket
import struct

# Statuses that mean "move_base is done with this goal"
TERMINAL = {
    GoalStatus.PREEMPTED,   # 2
    GoalStatus.SUCCEEDED,   # 3
    GoalStatus.ABORTED,     # 4
    GoalStatus.REJECTED,    # 5
    GoalStatus.RECALLED,    # 8
}

MOTION_HOST = ('192.168.137.103', 43893)

CMD_HEARTBEAT      = 0x31040001
CMD_CONFIRM_CONN   = 0x31020001
CMD_TOGGLE_STEPPING = 0x31010201

REACHED = 999 

class ReachPublisher(Node):

    def __init__(self) -> None:
        super().__init__('reach_publisher')

        self.goal_publisher = self.create_publisher(
            MoveBaseActionGoal, '/move_base/goal', 10)
        self.cancel_publisher = self.create_publisher(
            GoalID, '/move_base/cancel', 10)
        self.create_subscription(
            GoalArray, '/robot/goals', self.goal_callback, 10)
        # self.create_subscription(
        #     MoveBaseActionResult, '/move_base/result', self.result_callback, 10)
        self.create_subscription(
            std_msgs.msg.String, '/robot/cancel', self.cancel_callback, 10)
        self.create_subscription(
            std_msgs.msg.Int32, '/planner_status', self.planner_status_callback, 10)
        self.queue = deque()
        self.current_id = None
        self.cancel_current = False
        self.current_wait_time = 0
        self.wait_timer = None
        self.last_planner_status = None
        self.armed = False

        # UDP link to the motion host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.stepping = False   # our best guess of the robot's state
        self.create_timer(0.2, self.send_heartbeat)   # 5 Hz, above the 2 Hz minimum
        self.send_simple_command(CMD_CONFIRM_CONN)    # confirm connection once

    """UDP stream commands"""
    def send_simple_command(self, code: int, value: int = 0) -> None:
        # CommandHead: code, parameters_size, type (simple command => 0), little endian
        packet = struct.pack('<III', code, value, 0)
        try:
            self.sock.sendto(packet, MOTION_HOST)
        except OSError as e:
            self.get_logger().error(f'UDP send failed: {e}')

    def send_heartbeat(self) -> None:
        self.send_simple_command(CMD_HEARTBEAT)

    def toggle_stepping(self) -> None:
        self.send_simple_command(CMD_TOGGLE_STEPPING)
        self.stepping = not self.stepping
        self.get_logger().info(
            f'Stepping {"started" if self.stepping else "stopped"}')

    def start_stepping(self) -> None:
        if self.stepping:
            self.get_logger().info('Already stepping')
            return
        self.toggle_stepping()

    def stop_stepping(self) -> None:
        if not self.stepping:
            self.get_logger().info('Already not stepping')
            return
        self.toggle_stepping()


    """Robot commands"""
    def goal_callback(self, message: GoalArray) -> None:

        if not message.goals:
            self.get_logger().warn('Received empty GoalArray, ignoring')
            return

        self.queue.extend(message.goals)
        self.get_logger().info(f'Queued {len(self.queue)} goals')
        
        if self.current_id is None:
            self.send_next()

    def send_next(self) -> None:

        if not self.queue:
            self.current_id = None
            self.get_logger().info('All goals completed')
            self.stop_stepping()
            return
        
        self.start_stepping()
        goal = self.queue.popleft()

        if not goal.goalid:
            self.get_logger().warn('Goal has no id, skipping')
            self.send_next()
            return

        self.current_wait_time = goal.wait_time

        msg = MoveBaseActionGoal()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        self.current_id = goal.goalid
        msg.goal_id.id = self.current_id
        #msg.goal_id.stamp = msg.header.stamp

        msg.goal.target_pose.header.frame_id = "map"
        msg.goal.target_pose.pose.position.x = goal.goal.pose.position.x
        msg.goal.target_pose.pose.position.y = goal.goal.pose.position.y
        msg.goal.target_pose.pose.position.z = goal.goal.pose.position.z
        msg.goal.target_pose.pose.orientation.x = goal.goal.pose.orientation.x
        msg.goal.target_pose.pose.orientation.y = goal.goal.pose.orientation.y
        msg.goal.target_pose.pose.orientation.z = goal.goal.pose.orientation.z
        msg.goal.target_pose.pose.orientation.w = goal.goal.pose.orientation.w

        self.goal_publisher.publish(msg)
        self.get_logger().info(
            f'Sent goal {self.current_id} ({len(self.queue)} remaining)')



    def planner_status_callback(self, msg: std_msgs.msg.Int32) -> None:
        if self.current_id is None or self.wait_timer is not None:
            return
        if msg.data != REACHED:
            self.armed = True            # saw "not reached" since the goal was sent
        elif self.armed:
            self.armed = False
            self.handle_result(GoalStatus.SUCCEEDED, '')

    def handle_result(self, status, text) -> None:
        if status == GoalStatus.SUCCEEDED:
            self.get_logger().info(f'Goal {self.current_id} reached')
            if self.current_wait_time > 0:
                self.stop_stepping()
                self.get_logger().info(
                    f'Waiting {self.current_wait_time}s before next goal')
                self.wait_timer = self.create_timer(
                    float(self.current_wait_time), self.wait_done)
            else:
                self.send_next()
        else:
            self.get_logger().error(
                f'Goal {self.current_id} failed ({status}): {text}. '
                f'Aborting remaining goals.')
            self.queue.clear()
            self.current_id = None

    def wait_done(self) -> None:
        self.start_stepping()
        self.destroy_timer(self.wait_timer)   # makes it one-shot
        self.wait_timer = None
        self.send_next()

    def cancel_callback(self, message: std_msgs.msg.String) -> None:

        if self.wait_timer is not None:      # goal already done, we're just waiting
            self.destroy_timer(self.wait_timer)
            self.wait_timer = None
            self.get_logger().info(f'Cancelled wait after goal {message.data}')
            self.send_next()
            return
        
        if message.data == self.current_id:
            self.get_logger().info(f'Cancelling current goal {message.data}')
            self.cancel_current = True #Comment out if not connected to robot
            cancel_msg = GoalID()
            cancel_msg.id = self.current_id
            self.cancel_publisher.publish(cancel_msg)
            self.send_next() #Comment out if connected to robot
            return
        
        for goal in self.queue:
            if goal.goalid == message.data:
                self.queue.remove(goal)
                self.get_logger().info(f'Cancelled goal {message.data}')
                return
            
        self.get_logger().warn(f'Cancel requested for unknown goal {message.data}')

            
def main(args=None) -> None:
    rclpy.init(args=args)
    node = ReachPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
        node.sock.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()