"""Build the 2D occupancy map from /scan at FAST-LIO poses and publish it on /map.

The pose is map->base_link, so the saved map lives in the frame FAST-LIO localizes in during navigation.
Save it with `ros2 run x30_navigation save_map <world>`.
"""
import math

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener

import numpy as np

from .occupancy import OccupancyGrid2D


class GridMapper(Node):
    def __init__(self):
        super().__init__('grid_mapper')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('resolution', 0.05)
        self.declare_parameter('size_m', 100.0)
        self.declare_parameter('range_min', 0.6)
        self.declare_parameter('range_max', 12.0)
        self.declare_parameter('update_hz', 5.0)
        self.declare_parameter('publish_hz', 1.0)
        self.map_frame = self.get_parameter('map_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.range_min = float(self.get_parameter('range_min').value)
        self.range_max = float(self.get_parameter('range_max').value)
        self.grid = OccupancyGrid2D(float(self.get_parameter('resolution').value), float(self.get_parameter('size_m').value))
        self.min_period = 1.0 / float(self.get_parameter('update_hz').value)
        self.last_update = -1e9
        self.pending = None
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.publisher = self.create_publisher(OccupancyGrid, 'map', QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE))
        self.create_subscription(LaserScan, self.get_parameter('scan_topic').value, self.on_scan, qos_profile_sensor_data)
        self.create_timer(0.05, self.process_pending)
        self.create_timer(1.0 / float(self.get_parameter('publish_hz').value), self.publish_map)
        self.get_logger().info(f'Mapping {self.get_parameter("scan_topic").value} at {self.map_frame}->{self.base_frame}')

    def on_scan(self, scan):
        # FAST-LIO's pose for this scan arrives a little after the scan itself, so keep the newest scan and
        # retry from a timer until the transform is available.
        self.pending = scan

    def process_pending(self):
        scan = self.pending
        if scan is None:
            return
        stamp = Time.from_msg(scan.header.stamp)
        now = stamp.nanoseconds * 1e-9
        if now - self.last_update < self.min_period:
            self.pending = None
            return
        try:
            transform = self.tf_buffer.lookup_transform(self.map_frame, scan.header.frame_id, stamp)
        except TransformException as exc:
            if (self.get_clock().now() - stamp).nanoseconds * 1e-9 > 1.0:
                self.pending = None
                self.get_logger().warn(f'Dropped a scan, no {self.map_frame}->{scan.header.frame_id}: {exc}',
                                       throttle_duration_sec=5.0)
            return
        self.pending = None
        self.last_update = now
        t, q = transform.transform.translation, transform.transform.rotation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        angles = scan.angle_min + np.arange(len(scan.ranges)) * scan.angle_increment
        self.grid.integrate((t.x, t.y, yaw), angles, scan.ranges, max(self.range_min, scan.range_min), min(self.range_max, scan.range_max))

    def publish_map(self):
        packed = self.grid.to_message_data()
        if packed is None:
            return
        data, ox, oy, width, height = packed
        msg = OccupancyGrid()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.map_frame
        msg.info.resolution = self.grid.res
        msg.info.width, msg.info.height = int(width), int(height)
        msg.info.origin.position.x, msg.info.origin.position.y = float(ox), float(oy)
        msg.info.origin.orientation.w = 1.0
        msg.data = data.tolist()
        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = GridMapper()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
