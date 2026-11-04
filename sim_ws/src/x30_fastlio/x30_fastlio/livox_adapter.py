"""Convert the simulated lidar cloud `/lidar_points` into the Livox `CustomMsg` that FAST-LIO reads.

The sim cloud carries the real robot's 26-byte point layout (x, y, z, intensity, tag, line, timestamp in ms).
CustomMsg wants the scan start in `timebase` and, per point, the time since the scan start in ns in `offset_time`.
"""
import numpy as np
import rclpy
from livox_ros_driver2.msg import CustomMsg, CustomPoint
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2

_NP_FROM_DATATYPE = {1: 'i1', 2: 'u1', 3: '<i2', 4: '<u2', 5: '<i4', 6: '<u4', 7: '<f4', 8: '<f8'}
_MAX_OFFSET_NS = 2 ** 32 - 1


class LivoxAdapter(Node):
    def __init__(self):
        super().__init__('livox_adapter')
        self.declare_parameter('input_topic', '/lidar_points')
        self.declare_parameter('output_topic', '/livox/lidar')
        self.declare_parameter('lidar_id', 0)
        # Points the sim marks as "no return" sit at the sensor origin with intensity 0 (the real Mid-360 does the same).
        self.declare_parameter('drop_invalid', True)
        # Keep every n-th point; a Python message object per point is the cost of this node.
        self.declare_parameter('decimate', 3)
        self.lidar_id = int(self.get_parameter('lidar_id').value)
        self.drop_invalid = bool(self.get_parameter('drop_invalid').value)
        self.decimate = max(1, int(self.get_parameter('decimate').value))

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=3)
        self.pub = self.create_publisher(CustomMsg, self.get_parameter('output_topic').value, qos)
        self.create_subscription(PointCloud2, self.get_parameter('input_topic').value, self.on_cloud, qos)
        self.get_logger().info(
            f'{self.get_parameter("input_topic").value} -> {self.get_parameter("output_topic").value} '
            f'(decimate {self.decimate}, drop_invalid {self.drop_invalid})')

    @staticmethod
    def parse(msg: PointCloud2) -> np.ndarray:
        dt = np.dtype({
            'names': [f.name for f in msg.fields],
            'formats': [_NP_FROM_DATATYPE[f.datatype] for f in msg.fields],
            'offsets': [f.offset for f in msg.fields],
            'itemsize': msg.point_step,
        })
        return np.frombuffer(bytes(msg.data), dtype=dt, count=msg.width * msg.height)

    def on_cloud(self, msg: PointCloud2) -> None:
        arr = self.parse(msg)
        if self.drop_invalid:
            arr = arr[arr['intensity'] > 0]
        arr = arr[::self.decimate]

        t0_ns = msg.header.stamp.sec * 10 ** 9 + msg.header.stamp.nanosec
        offset = np.clip((arr['timestamp'] - t0_ns * 1e-6) * 1e6, 0, _MAX_OFFSET_NS).astype(np.uint32)
        refl = np.clip(arr['intensity'], 0, 255).astype(np.uint8)

        out = CustomMsg()
        out.header = msg.header
        out.timebase = t0_ns
        out.lidar_id = self.lidar_id
        out.point_num = len(arr)
        out.points = [
            CustomPoint(offset_time=int(o), x=float(x), y=float(y), z=float(z), reflectivity=int(r), tag=int(t), line=int(ln))
            for o, x, y, z, r, t, ln in zip(offset.tolist(), arr['x'].tolist(), arr['y'].tolist(), arr['z'].tolist(),
                                            refl.tolist(), arr['tag'].tolist(), arr['line'].tolist())
        ]
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = LivoxAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
