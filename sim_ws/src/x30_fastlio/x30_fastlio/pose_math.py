"""Rigid-transform helpers for the FAST-LIO localizer (4x4 homogeneous matrices)."""

import math

import numpy as np


def matrix(translation, quaternion):
    """4x4 transform from (x, y, z) and an (x, y, z, w) quaternion."""
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    out = np.eye(4)
    out[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    out[:3, 3] = translation
    return out


def inverse(transform):
    out = np.eye(4)
    rotation = transform[:3, :3].T
    out[:3, :3] = rotation
    out[:3, 3] = -rotation @ transform[:3, 3]
    return out


def planar(transform):
    """(x, y, yaw) of a transform; roll, pitch and height are dropped (the robot navigates in 2D)."""
    return transform[0, 3], transform[1, 3], math.atan2(transform[1, 0], transform[0, 0])


def map_to_odom(t_map_imu, t_base_imu, t_odom_base):
    """Planar map->odom so that map->base_link equals the FAST-LIO estimate.

    t_map_imu: FAST-LIO pose of the IMU (body) in its start frame, used as the map frame.
    t_base_imu: pose of the IMU in base_link (static mounting).
    t_odom_base: pose of base_link in the odometry frame.
    """
    t_map_base = t_map_imu @ inverse(t_base_imu)
    return planar(t_map_base @ inverse(t_odom_base))
