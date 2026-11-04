import numpy as np

from x30_fastlio.occupancy import OccupancyGrid2D


def square_room(grid, pose, half=3.0, rays=360):
    angles = np.linspace(-np.pi, np.pi, rays, endpoint=False)
    # distance to the walls of an axis-aligned square room centred on the origin
    ranges = []
    for a in angles:
        dx, dy = np.cos(a), np.sin(a)
        candidates = [(half - pose[0]) / dx if dx > 1e-9 else (-half - pose[0]) / dx if dx < -1e-9 else np.inf,
                      (half - pose[1]) / dy if dy > 1e-9 else (-half - pose[1]) / dy if dy < -1e-9 else np.inf]
        ranges.append(min(candidates))
    for _ in range(3):  # a few scans so the free space accumulates beyond the cell threshold
        grid.integrate(pose, angles - pose[2], ranges, 0.3, 20.0)


def test_room_walls_occupied_inside_free():
    grid = OccupancyGrid2D(0.1, 20.0)
    square_room(grid, (0.0, 0.0, 0.0))
    data, ox, oy, w, h = grid.to_message_data()
    image = data.reshape(h, w)

    def cell(x, y):
        return image[int((y - oy) / 0.1), int((x - ox) / 0.1)]
    assert cell(0.0, 0.0) == 0 and cell(1.5, -1.0) == 0
    assert cell(3.0, 0.0) == 100 and cell(0.0, -3.0) == 100
    assert cell(3.8, 3.8) == -1          # outside the room: never seen


def test_scan_pose_yaw_is_applied():
    grid = OccupancyGrid2D(0.1, 20.0)
    for _ in range(3):
        grid.integrate((0.0, 0.0, np.pi / 2), [0.0], [2.0], 0.3, 20.0)   # ray along +y
    data, ox, oy, w, h = grid.to_message_data()
    image = data.reshape(h, w)
    assert image[int((2.0 - oy) / 0.1), int((0.0 - ox) / 0.1)] == 100


def test_no_returns_and_nothing_seen():
    grid = OccupancyGrid2D(0.1, 20.0)
    assert grid.to_message_data() is None
    grid.integrate((0, 0, 0), [0.0], [float('inf')], 0.3, 20.0)
    assert grid.to_message_data() is None
