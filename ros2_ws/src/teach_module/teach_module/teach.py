import json
import os
import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from tf2_msgs.msg import TFMessage

JSON_file = os.path.expanduser("~/ros2_ws/src/qwen_voice_manager/config/map.json")

class Robot_sub(Node):

    def __init__(self):
        super().__init__('teach')
        self.subscription = self.create_subscription(
            TFMessage,
            '/tf',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        self.get_logger().info(msg.data)


class Qwen_sub(Node):

    def __init__(self):
        super().__init__('teach')
        self.subscription = self.create_subscription(
            String,
            '/robot/teach', 
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        self.get_logger().info(msg.data)
        if msg.data == "teach":
            teach_point(self, 1.0, 2.0, 0.0, "TestPoint", "This point was made for testing")



#def main(args=None):
    # rclpy.init(args=args)

    # robot_odom = Robot_sub()
    # robot_odom.get_logger().info('Robot subscriber node has been started.')
    # qwen_sub = Qwen_sub()
    # qwen_sub.get_logger().info('Qwen subscriber node has been started.')

    # rclpy.spin(robot_odom)
    # rclpy.spin(qwen_sub)

    # # Destroy the node explicitly
    # # (optional - otherwise it will be done automatically
    # # when the garbage collector destroys the node object)
    # robot_odom.destroy_node()
    # qwen_sub.destroy_node()
    # rclpy.shutdown()
def main(args=None):
    rclpy.init(args=args)

    robot_odom = Robot_sub()
    qwen_sub = Qwen_sub()

    robot_odom.get_logger().info('Robot subscriber node has been started.')
    qwen_sub.get_logger().info('Qwen subscriber node has been started.')

    executor = rclpy.executors.SingleThreadedExecutor()

    executor.add_node(robot_odom)
    executor.add_node(qwen_sub)

    try:
        executor.spin()

    finally:
        executor.remove_node(robot_odom)
        executor.remove_node(qwen_sub)

        robot_odom.destroy_node()
        qwen_sub.destroy_node()

        rclpy.shutdown()


def teach_point(self, x, y, orientation, name, descriptor):


    #Append Point to JSON file
    if os.path.exists(JSON_file):
        with open(JSON_file, 'r') as file:
            waypoints = json.load(file)
            waypoints.append({
                "x": x,
                "y": y,
                "orientation": orientation,
                "name": name,
                "descriptor": descriptor
                })

        with open(JSON_file, 'w') as file:
            json.dump(waypoints, file, indent=4)

        self.get_logger().info('Point added to JSON file.')
    else:
        self.get_logger().info('Could not find JSON file."')



if __name__ == '__main__':
    main()