import math

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node


class InitialPosePublisher(Node):
	def __init__(self):
		super().__init__('initial_pose_publisher')

		self.declare_parameter('x', 0.0)
		self.declare_parameter('y', 0.0)
		self.declare_parameter('yaw', 0.0)
		self.declare_parameter('frame_id', 'map')
		self.declare_parameter('covariance_x', 0.25)
		self.declare_parameter('covariance_y', 0.25)
		self.declare_parameter('covariance_yaw', 0.0685)

		self.publisher = self.create_publisher(
			PoseWithCovarianceStamped, '/initialpose', 10
		)
		self.timer = self.create_timer(0.5, self.publish_initial_pose)

	def publish_initial_pose(self):
		# Wait for localization to subscribe so the one-shot message is received.
		if self.publisher.get_subscription_count() == 0:
			return

		x = self.get_parameter('x').value
		y = self.get_parameter('y').value
		yaw = self.get_parameter('yaw').value

		message = PoseWithCovarianceStamped()
		message.header.stamp = self.get_clock().now().to_msg()
		message.header.frame_id = self.get_parameter('frame_id').value
		message.pose.pose.position.x = x
		message.pose.pose.position.y = y
		message.pose.pose.orientation.z = math.sin(yaw / 2.0)
		message.pose.pose.orientation.w = math.cos(yaw / 2.0)

		covariance = [0.0] * 36
		covariance[0] = self.get_parameter('covariance_x').value
		covariance[7] = self.get_parameter('covariance_y').value
		covariance[35] = self.get_parameter('covariance_yaw').value
		message.pose.covariance = covariance

		self.publisher.publish(message)
		self.get_logger().info('Published initial pose to /initialpose')
		self.timer.cancel()


def main(args=None):
	rclpy.init(args=args)
	node = InitialPosePublisher()
	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		node.destroy_node()
		rclpy.shutdown()


if __name__ == '__main__':
	main()
