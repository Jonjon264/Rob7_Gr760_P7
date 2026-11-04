"""Turn robot/goals, robot/cancel and robot/teach into Nav2 actions on the simulated robot."""

import rclpy
from interfaces.msg import CustomTeach, GoalArray
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener

from . import places
from .mapgeom import MapGeometry
from .goal_queue import GoalQueue


class TaskExecutor(Node):
    def __init__(self, **kwargs):
        super().__init__('x30_task_executor', **kwargs)
        self.declare_parameter('goals_topic', 'robot/goals')
        self.declare_parameter('cancel_topic', 'robot/cancel')
        self.declare_parameter('teach_topic', 'robot/teach')
        self.declare_parameter('status_topic', 'robot/status')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        # Same file the voice manager reads; teach requests edit it.
        self.declare_parameter('map_file', '')
        # Waypoints made with Map/Labeling.py are image pixels. With a map yaml they are converted to metres
        # for Nav2, and taught places are stored back as pixels. Without one, coordinates are taken as metres.
        self.declare_parameter('map_yaml', '')
        yaml_path = self.get_parameter('map_yaml').value
        self.geometry = MapGeometry(yaml_path) if yaml_path else None

        self.queue = GoalQueue()
        self._goal_handle = None
        self._cancelling = False
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.nav = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.status = self.create_publisher(String, self.get_parameter('status_topic').value, 10)
        self.create_subscription(GoalArray, self.get_parameter('goals_topic').value, self.on_goals, 10)
        self.create_subscription(String, self.get_parameter('cancel_topic').value, self.on_cancel, 10)
        self.create_subscription(CustomTeach, self.get_parameter('teach_topic').value, self.on_teach, 10)
        self.get_logger().info('Task executor ready; waiting for goals')

    def report(self, text):
        self.get_logger().info(text)
        self.status.publish(String(data=text))

    # --- goals -------------------------------------------------------------------------
    def on_goals(self, array):
        goals = [(g.goalid, g.goal) for g in array.goals]
        interrupt = self.queue.replace(goals)
        self.report(f'Received {len(goals)} goal(s): {[g[0] for g in goals]}')
        if interrupt:
            self._cancel_active()  # the result callback then starts the new queue
        else:
            self._send_next()

    def _send_next(self):
        goal = self.queue.next()
        if goal is None:
            return
        goal_id, pose = goal
        if not self.nav.wait_for_server(timeout_sec=2.0):
            self.report(f'Nav2 navigate_to_pose is not available; dropping goal {goal_id}')
            self.queue.finish()
            self.queue.pending.clear()
            return
        pose.header.stamp = Time().to_msg()  # latest transform instead of the publish time
        if self.geometry:
            pose.pose.position.x, pose.pose.position.y = self.geometry.pixel_to_world(
                pose.pose.position.x, pose.pose.position.y)
        request = NavigateToPose.Goal()
        request.pose = pose
        self.report(f'Navigating to {goal_id}')
        self.nav.send_goal_async(request).add_done_callback(self._on_accepted)

    def _on_accepted(self, future):
        handle = future.result()
        if not handle.accepted:
            self.report(f'Nav2 rejected goal {self.queue.active[0]}')
            self._finished()
            return
        self._goal_handle = handle
        if self._cancelling:
            self._cancel_active()
            return
        handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        status = future.result().status
        goal_id = self.queue.active[0] if self.queue.active else '?'
        # 4 = succeeded, 5 = canceled, 6 = aborted (action_msgs/GoalStatus)
        self.report({4: f'Reached {goal_id}', 5: f'Cancelled {goal_id}'}.get(
            status, f'Navigation to {goal_id} failed (status {status})'))
        if status == 6:
            self.queue.pending.clear()  # do not continue a route past a failed leg
        self._finished()

    def _finished(self):
        self._goal_handle = None
        self._cancelling = False
        self.queue.finish()
        self._send_next()

    def _cancel_active(self):
        if self._goal_handle is None:
            self._cancelling = True  # goal still being accepted; cancel as soon as it is
            return
        self._goal_handle.cancel_goal_async()

    # --- cancel ------------------------------------------------------------------------
    def on_cancel(self, message):
        removed, cancel_active = self.queue.cancel(message.data)
        self.report(f'Cancel {message.data or "all"}: removed {removed} queued goal(s)'
                    f'{", cancelling the active goal" if cancel_active else ""}')
        if cancel_active:
            self._cancel_active()

    # --- teach -------------------------------------------------------------------------
    def on_teach(self, message):
        map_file = self.get_parameter('map_file').value
        if not map_file:
            self.report('Teach ignored: the map_file parameter is not set')
            return
        try:
            if message.action == CustomTeach.TEACH:
                x, y = self._robot_position()
                if self.geometry:
                    x, y = self.geometry.world_to_pixel(x, y)
                places.add_place(map_file, message.place_id, message.description, x, y)
                self.report(f'Taught place {message.place_id} at ({x}, {y})')
            else:
                count = places.remove_place(map_file, message.place_id)
                self.report(f'Removed {count} place(s) named {message.place_id}')
        except (TransformException, OSError, ValueError) as exc:
            self.report(f'Teach failed: {exc}')

    def _robot_position(self):
        transform = self.tf_buffer.lookup_transform(
            self.get_parameter('map_frame').value, self.get_parameter('base_frame').value, Time())
        return transform.transform.translation.x, transform.transform.translation.y


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TaskExecutor()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
