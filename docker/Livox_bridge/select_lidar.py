"""Forward one device's native messages from /livox/lidar to /mapping/lidar."""
import os

import rclpy
from livox_ros_driver2.msg import CustomMsg
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


class SelectLidar(Node):
    def __init__(self):
        super().__init__("select_lidar")
        self.lidar_id = int(os.environ["LIVOX_LIDAR_ID"])
        if not 0 <= self.lidar_id <= 255:
            raise ValueError("LIVOX_LIDAR_ID must be between 0 and 255")
        qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE)
        self.publisher = self.create_publisher(CustomMsg, "/mapping/lidar", qos)
        self.subscription = self.create_subscription(
            CustomMsg, "/livox/lidar", self.receive, qos
        )
        self.get_logger().info(f"Forwarding only lidar_id={self.lidar_id}")

    def receive(self, message):
        if message.lidar_id == self.lidar_id:
            self.publisher.publish(message)


def main():
    rclpy.init()
    node = SelectLidar()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
