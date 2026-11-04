"""Checks for the migrated world registry and camera placement at remote spawns."""
import math
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from x30_sim import geometry, gui_config, worlds


def test_hospital_uses_migrated_registry_and_spawn():
    spec = worlds.resolve_world('aws_hospital')
    assert spec.sdf.is_file()
    world = ET.parse(spec.sdf).getroot().find('world')
    assert world.get('name') == 'aws_hospital'
    assert spec.spawn == {'x': 0.93, 'y': 11.48, 'z': 0.0, 'yaw': 0.0}
    # The robot supplies IMU processing, and the imported mesh supplies the floor.
    assert not world.findall("plugin[@filename='gz-sim-imu-system']")
    assert world.find("model[@name='ground_plane']/link/collision") is not None
    assert world.find("model[@name='ground_plane']/link/visual") is None


@pytest.mark.parametrize('yaw', [0.0, math.pi / 2])
def test_gui_camera_faces_robot_at_nonzero_spawn(tmp_path, yaw):
    template = tmp_path / 'template.config'
    template.write_text('<plugin><camera_pose>-6 0 6 0 0.5 0</camera_pose></plugin>')
    target = np.array([10.0, 20.0, 0.5])
    output = gui_config.write_for_spawn(template, tmp_path / 'gui.config', *target, yaw)
    pose = np.array([float(value) for value in ET.parse(output).getroot().findtext('camera_pose').split()])
    direction = geometry.rpy_matrix(*pose[3:])[:, 0]
    expected = target - pose[:3]
    expected /= np.linalg.norm(expected)
    assert direction == pytest.approx(expected, abs=1e-7)
    assert target[2] < pose[2] < 2.65  # Inside the room, below its ceiling.
