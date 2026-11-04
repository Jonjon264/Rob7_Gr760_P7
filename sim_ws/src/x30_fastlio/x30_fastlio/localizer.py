"""Publish map->odom from FAST-LIO so that Nav2 localizes with the lidar-inertial estimate.

FAST-LIO reports the IMU pose in its own start frame (`camera_init`). That frame is used as `map`.
The simulator already provides odom->base_link; this node publishes the planar map->odom that makes
map->base_link equal FAST-LIO's estimate, the same job AMCL or SLAM Toolbox does in the usual Nav2 setup.
"""
import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformBroadcaster, TransformException, TransformListener

from . import pose_math


def _stamped_matrix(transform):
    t, q = transform.transform.translation, transform.transform.rotation
    return pose_math.matrix((t.x, t.y, t.z), (q.x, q.y, q.z, q.w))


class FastlioLocalizer(Node):
    def __init__(self):
        super().__init__('fastlio_localizer')
        self.declare_parameter('odometry_topic', '/Odometry')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('imu_frame', 'imu_link')
        # A scan-to-scan change of map->odom larger than this means FAST-LIO has diverged; the last good value is kept.
        self.declare_parameter('max_step_m', 0.3)
        self.declare_parameter('max_step_rad', 0.3)
        self.map_frame = self.get_parameter('map_frame').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.imu_frame = self.get_parameter('imu_frame').value
        self.t_base_imu = None
        self.last_good = None
        self.rejected = 0
        self.max_step_m = float(self.get_parameter('max_step_m').value)
        self.max_step_rad = float(self.get_parameter('max_step_rad').value)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.broadcaster = TransformBroadcaster(self)
        self.create_subscription(Odometry, self.get_parameter('odometry_topic').value, self.on_odometry, 10)
        self.get_logger().info(f'Publishing {self.map_frame}->{self.odom_frame} from FAST-LIO')

    def on_odometry(self, msg):
        stamp = Time.from_msg(msg.header.stamp)
        try:
            if self.t_base_imu is None:  # static mounting, read once
                self.t_base_imu = _stamped_matrix(self.tf_buffer.lookup_transform(
                    self.base_frame, self.imu_frame, Time(), Duration(seconds=0.5)))
            t_odom_base = _stamped_matrix(self.tf_buffer.lookup_transform(
                self.odom_frame, self.base_frame, stamp, Duration(seconds=0.1)))
        except TransformException as exc:
            self.get_logger().warn(f'Waiting for transforms: {exc}', throttle_duration_sec=5.0)
            return
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        t_map_imu = pose_math.matrix((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))
        x, y, yaw = pose_math.map_to_odom(t_map_imu, self.t_base_imu, t_odom_base)
        if self.last_good is not None:
            lx, ly, lyaw = self.last_good
            step_yaw = abs(math.atan2(math.sin(yaw - lyaw), math.cos(yaw - lyaw)))
            if math.hypot(x - lx, y - ly) > self.max_step_m or step_yaw > self.max_step_rad:
                self.rejected += 1
                if self.rejected == 1 or self.rejected % 100 == 0:
                    self.get_logger().error(
                        f'FAST-LIO jumped {math.hypot(x - lx, y - ly):.2f} m / {step_yaw:.2f} rad; keeping the last good '
                        f'{self.map_frame}->{self.odom_frame}. It does not recover: restart FAST-LIO.')
                x, y, yaw = self.last_good
            else:
                self.rejected = 0
        self.last_good = (x, y, yaw)
        out = TransformStamped()
        out.header.stamp = msg.header.stamp
        out.header.frame_id, out.child_frame_id = self.map_frame, self.odom_frame
        out.transform.translation.x, out.transform.translation.y = x, y
        out.transform.rotation.z, out.transform.rotation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self.broadcaster.sendTransform(out)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = FastlioLocalizer()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
