import threading
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from std_msgs.msg import String
from .agent import QwenAgent 
from qwen_voice_manager.speaker import ReplyPlayer

class GoalImageNode(Node):
    def __init__(self):
        super().__init__('goal_image_node')
        self.player = ReplyPlayer() 
        self.max_attempts = 5
        self.retry_delay = 5.0           # seconds between photos
        self.delivery_confirmed_pub = self.create_publisher(Bool, 'delivery_confirmed', 10)



        
        self.declare_parameter('goal_topic', 'delivery_goal_reached')
        self.declare_parameter('image_topic', '/camera/camera/color/image_raw')
        self.declare_parameter('Transcript_topic', 'manager/transcripts')
        self.declare_parameter('max_image_width', 640)  # 0 = no resizing
        self.declare_parameter('text_topic', 'manager/text') #check this

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

    def encode_latest_frame(self):
        if self.latest_image is None:
            return None
        frame = self.bridge.imgmsg_to_cv2(self.latest_image, desired_encoding='bgr8')
        if self.max_width and frame.shape[1] > self.max_width:
            scale = self.max_width / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        return buf.tobytes() if ok else None

    def goal_callback(self, msg):
        activated = msg.data and not self.last_goal
        self.last_goal = msg.data
        if not activated:
            return
        if self.latest_image is None:
            self.get_logger().warn('Goal reached but no image received yet')
            return
        jpeg = self.encode_latest_frame()   # frame at the moment of the goal
        if jpeg is None:
            self.get_logger().error('JPEG encoding failed')
            return
        threading.Thread(target=self.agent_worker, args=(jpeg,), daemon=True).start()

        # The model call can take up to the 180 s timeout, so run it in a thread;
        # otherwise the executor would stall and stop processing camera frames

    def transcript_callback(self, msg):
        self.latest_transcript = msg.data
        self.get_logger().info(f'Received text: {msg.data}')
        



    def agent_worker(self, jpeg_bytes):
        # Hold the lock for the whole interaction so a second goal can't start another one
        if not self.agent_lock.acquire(blocking=False):
            self.get_logger().warn('Agent call already in progress, skipping')
            return
        try:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    reply = self.agent.ask(self.latest_transcript, jpeg_bytes)
                except Exception as e:
                    self.get_logger().error(f'Agent call failed: {e}')
                    return

                self.get_logger().info(f'Attempt {attempt}: {reply}')
                match = reply["match"]
                response = str(reply["response"])

                # Speak whatever the agent said (greeting or "please step into frame")
                self.player.submit(response)

                if match:
                    self.get_logger().info(f'Match found: {response}')
                    self.delivery_confirmed_pub.publish(Bool(data=True))
                    return                      # end process

                self.get_logger().info(f'No match: {response}')
                time.sleep(self.retry_delay)    # let the person step into frame

                # Take a NEW photo for the next attempt
                jpeg_bytes = self.encode_latest_frame()
                if jpeg_bytes is None:
                    self.get_logger().error('Could not get a new frame, aborting')
                    return

            self.get_logger().warn(f'No match after {self.max_attempts} attempts, giving up')
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
            node.player.close()
            rclpy.shutdown()




if __name__ == '__main__':
    main()
    



#Take Agent response 
#if match is true, call TTS using the response to greet them and tell them to get their package and to confirm delivery. End process
#if match is false, call TTS using the response to tell the person to step into frame prompt new photo after a few seconds and repeat the process.
