import math

import numpy as np

from x30_fastlio import pose_math as pm


def yaw_q(yaw):
    return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


def test_matrix_inverse_roundtrip():
    t = pm.matrix((1.0, -2.0, 0.5), yaw_q(0.7))
    assert np.allclose(t @ pm.inverse(t), np.eye(4))


def test_identity_when_fastlio_agrees_with_odometry():
    t_base_imu = pm.matrix((0.13045, -0.001, 0.0149), (0, 0, 0, 1))
    t_odom_base = pm.matrix((2.0, 1.0, 0.0), yaw_q(0.5))
    # FAST-LIO agrees with the odometry: base_link is at the same pose in both frames.
    t_map_base = t_odom_base
    t_map_imu = t_map_base @ t_base_imu
    x, y, yaw = pm.map_to_odom(t_map_imu, t_base_imu, t_odom_base)
    assert max(abs(x), abs(y), abs(yaw)) < 1e-9


def test_offset_between_estimates_is_recovered():
    t_base_imu = pm.matrix((0.1, 0.0, 0.0), (0, 0, 0, 1))
    t_odom_base = pm.matrix((1.0, 0.0, 0.0), (0, 0, 0, 1))
    # FAST-LIO thinks the robot is 0.5 m further along x and rotated by 90 degrees.
    t_map_base = pm.matrix((1.5, 0.0, 0.0), yaw_q(math.pi / 2))
    x, y, yaw = pm.map_to_odom(t_map_base @ t_base_imu, t_base_imu, t_odom_base)
    recomposed = pm.matrix((x, y, 0.0), yaw_q(yaw)) @ t_odom_base
    assert np.allclose(recomposed, t_map_base, atol=1e-9)
