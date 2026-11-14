import os
import threading
from datetime import datetime

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool


class GoalImageNode(Node):
    def __init__(self):
        super().__init__('goal_image_node')

        self.declare_parameter('goal_topic', 'delivery_goal_reached') #delivery goal topic
        self.declare_parameter('image_topic', '/camera/camera/color/image_raw') #image topic

        goal_topic = self.get_parameter('goal_topic').value
        image_topic = self.get_parameter('image_topic').value
        self.prompt = self.get_parameter('prompt').value
        os.makedirs(self.save_dir, exist_ok=True)

        self.bridge = CvBridge()
        self.latest_image = None   # newest sensor_msgs/Image
        self.last_goal = False     # for detecting False -> True changes
        self.agent_lock = threading.Lock()  # prevents overlapping agent calls

        # Subscriber 1: images (keeps only the newest frame)
        self.create_subscription(
            Image, image_topic, self.image_callback, qos_profile_sensor_data)

        # Subscriber 2: delivery goal flag
        self.create_subscription(
            Bool, goal_topic, self.goal_callback, 10)

        self.get_logger().info(f'Listening on {goal_topic} and {image_topic}')

    # ---------- Subscriber 1: images ----------
    def image_callback(self, msg):
        self.latest_image = msg

    # ---------- Subscriber 2: goal ----------
    def goal_callback(self, msg):
        activated = msg.data and not self.last_goal
        self.last_goal = msg.data
        if not activated or self.latest_image is None:
            return

        frame = self.bridge.imgmsg_to_cv2(self.latest_image, desired_encoding='bgr8')
        ok, buf = cv2.imencode('.jpg', frame)
        if not ok:
            return

        try:
            response = self.send_image_to_agent(buf.tobytes())
            self.get_logger().info(f'Agent response: {response}')
        except Exception as e:
            self.get_logger().error(f'Agent call failed: {e}')

    # ---------- Agent call ----------
    def agent_worker(self, jpeg_bytes, prompt):
        if not self.agent_lock.acquire(blocking=False):
            self.get_logger().warn('Agent call already in progress, skipping')
            return
        try:
            response = self.send_image_to_agent(jpeg_bytes, prompt)
            self.get_logger().info(f'Agent response: {response}')
        except Exception as e:
            self.get_logger().error(f'Agent call failed: {e}')
        finally:
            self.agent_lock.release()

    def send_image_to_agent(self, jpeg_bytes):
        """PLACEHOLDER: send the image and prompt to your AI agent.

        jpeg_bytes: the image encoded as JPEG
        Return the agent's response (string, dict, ...).
        """
        self.get_logger().info(
            f'[placeholder] would send {len(jpeg_bytes)} bytes ')
        return None


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