import threading

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from std_msgs.msg import String
from .agent import QwenAgent 


class GoalImageNode(Node):
    def __init__(self):
        super().__init__('goal_image_node')

        self.declare_parameter('goal_topic', 'delivery_goal_reached')
        self.declare_parameter('image_topic', '/camera/camera/color/image_raw')
        self.declare_parameter('Transcript_topic', 'manager/transcripts')
        self.declare_parameter('max_image_width', 640)  # 0 = no resizing

        goal_topic = self.get_parameter('goal_topic').value
        image_topic = self.get_parameter('image_topic').value
        transcript_topic = self.get_parameter('Transcript_topic').value
        self.max_width = self.get_parameter('max_image_width').value

        self.bridge = CvBridge()
        self.agent = QwenAgent()
        self.latest_image = None
        self.last_goal = False
        self.agent_lock = threading.Lock()
        self.latest_transcript = None

        self.create_subscription(
            Image, image_topic, self.image_callback, qos_profile_sensor_data)
        self.create_subscription(Bool, goal_topic, self.goal_callback, 10)
        self.create_subscription(String, transcript_topic, self.transcript_callback,10)
        self.get_logger().info(f'Listening on {goal_topic}, {transcript_topic}, and {image_topic}')

    def image_callback(self, msg):
        self.latest_image = msg

    def goal_callback(self, msg):
        activated = msg.data and not self.last_goal   # False -> True only
        self.last_goal = msg.data
        if not activated:
            return
        if self.latest_image is None:
            self.get_logger().warn('Goal reached but no image received yet')
            return

        # Encode here (fast), so the frame is the one at the moment of the goal.
        frame = self.bridge.imgmsg_to_cv2(self.latest_image, desired_encoding='bgr8')
        if self.max_width and frame.shape[1] > self.max_width:
            scale = self.max_width / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            self.get_logger().error('JPEG encoding failed')
            return

        # The model call can take up to the 180 s timeout, so run it in a thread;
        # otherwise the executor would stall and stop processing camera frames.
        threading.Thread(
            target=self.agent_worker,
            args=(buf.tobytes(), self.latest_transcript),
            daemon=True,
        ).start()
    def transcript_callback(self, msg):
        self.latest_transcript = msg.data
        self.get_logger().info(f'Received text: {msg.data}')
        



    def agent_worker(self, jpeg_bytes, prompt):
        if not self.agent_lock.acquire(blocking=False):
            self.get_logger().warn('Agent call already in progress, skipping')
            return
        try:
            commands, spoken = self.agent.ask(prompt, jpeg_bytes)
            self.get_logger().info(f'Agent commands: {commands}')
            self.get_logger().info(f'Agent reply: {spoken}')
            # TODO: publish `commands` / speak `spoken` here if needed
        except Exception as e:
            self.get_logger().error(f'Agent call failed: {e}')
        finally:
            self.agent_lock.release()


def main(args=None):
    rclpy.init(args=args)
    node = GoalImageNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

#Publish på /robot/Continue (Bool = True)