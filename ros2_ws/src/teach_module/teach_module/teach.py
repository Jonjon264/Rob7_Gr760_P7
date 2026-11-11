import json
import os
import rclpy
from rclpy.node import Node

from interfaces.msg import CustomTeach
from nav_msgs.msg import Odometry

JSON_file = os.path.expanduser("~/ros2_ws/config/map.json")

px, py, ox, oy, oz, ow = 0.0, 0.0, 0.0, 0.0, 0.0, 1.0

class Robot_sub(Node):

    def __init__(self):
        super().__init__('teach')
        self.subscription = self.create_subscription(
            Odometry,
            '/odom',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        global px, py, ox, oy, oz, ow
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        ox = msg.pose.pose.orientation.x
        oy = msg.pose.pose.orientation.y
        oz = msg.pose.pose.orientation.z
        ow = msg.pose.pose.orientation.w



class Qwen_sub(Node):

    def __init__(self):
        super().__init__('teach')
        self.subscription = self.create_subscription(
            CustomTeach,
            '/robot/teach', 
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        action = msg.action
        place_id = msg.place_id
        description = msg.description

        self.get_logger().info(
            f"Action: {action}, "
            f"Place ID: {place_id}, "
            f"Description: {description}"
        )
        if action == 0:
            teach_point(self, px, py, (ox, oy, oz, ow), place_id, description)
        elif action == 1:
            delete_point(self, place_id)
        elif action == 2:
            delete_this_point(self, px, py)



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

def delete_point(self, name):
    #Delete Point from JSON file
    if os.path.exists(JSON_file):
        with open(JSON_file, 'r') as file:
            waypoints = json.load(file)
            waypoints = [point for point in waypoints if point["name"] != name]

        with open(JSON_file, 'w') as file:
            json.dump(waypoints, file, indent=4)

        self.get_logger().info('Point deleted from JSON file.')
    else:
        self.get_logger().info('Could not find JSON file."')

def delete_this_point(self, x, y):
    #Deleting the closest point to the robot's current position from the JSON file
    threshold_distance = 2.0
    self.get_logger().info(f"Current position: x={x}, y={y}")
    if os.path.exists(JSON_file):
        with open(JSON_file, 'r') as file:
            waypoints = json.load(file)
            closest_point = None
            closest_distance = float('inf')

            for point in waypoints:
                distance = ((point["x"] - x) ** 2 + (point["y"] - y) ** 2) ** 0.5
                if distance < closest_distance:
                    closest_distance = distance
                    closest_point = point

            if closest_point is not None and closest_distance < threshold_distance:
                waypoints.remove(closest_point)

            else:
                self.get_logger().info(f'No point found within {threshold_distance} meters of the current position.')
                return

        with open(JSON_file, 'w') as file:
            json.dump(waypoints, file, indent=4)

        self.get_logger().info('Closest point deleted from JSON file.')



if __name__ == '__main__':
    main()