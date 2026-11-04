"""Position the initial GUI camera behind the robot's chosen spawn pose."""
import math
from pathlib import Path
import re


def write_for_spawn(template: Path, output: Path, x: float, y: float, z: float, yaw: float) -> Path:
    distance, rise = 2.2, 1.3
    pose = (x - distance * math.cos(yaw), y - distance * math.sin(yaw), z + rise,
            0.0, math.atan2(rise, distance), yaw)
    camera = '<camera_pose>' + ' '.join(f'{value:.8f}' for value in pose) + '</camera_pose>'
    text, count = re.subn(r'<camera_pose>[^<]*</camera_pose>', camera, template.read_text(), count=1)
    if count != 1:
        raise ValueError(f'No camera_pose in Gazebo GUI template {template}')
    output.write_text(text)
    return output
