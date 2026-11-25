
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class DummyNode(Node):
    def __init__(self):
        super().__init__('dummy_node')

        self.get_logger().info('Dummy node has been started.')

        self.TestPub_Goal = self.create_publisher(
            Bool,
            '/robot/delivery_goal_reached',
            10
        )

        self.TestPub_Transcript = self.create_publisher(
            String,
            '/manager/transcripts',
            10
        )

        # Publish once when the node starts
        self.publish_goal()
        self.publish_transcript()

    def publish_goal(self):
        msg = Bool()
        msg.data = True

        self.TestPub_Goal.publish(msg)

    def publish_transcript(self):
        msg = String()
        msg.data = "Give this package to Simon"

        self.TestPub_Transcript.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = DummyNode()

    # Allow publishers to send their messages
    rclpy.spin_once(node, timeout_sec=0.5)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
