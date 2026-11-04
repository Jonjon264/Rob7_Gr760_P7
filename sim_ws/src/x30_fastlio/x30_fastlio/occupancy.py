"""Log-odds occupancy grid updated from 2D scans at known poses (no ROS imports, so it is unit-testable)."""

import numpy as np


class OccupancyGrid2D:
    def __init__(self, resolution=0.05, size_m=100.0, l_hit=0.85, l_free=-0.4, l_min=-5.0, l_max=5.0):
        self.res = resolution
        self.cells = int(round(size_m / resolution))
        self.origin = -size_m / 2.0          # world coordinate of cell (0, 0); the grid is centred on the start pose
        self.log_odds = np.zeros((self.cells, self.cells), np.float32)   # [row = y, col = x]
        self.touched = np.zeros((self.cells, self.cells), bool)
        self.l_hit, self.l_free, self.l_min, self.l_max = l_hit, l_free, l_min, l_max

    def _index(self, x, y):
        return np.floor((y - self.origin) / self.res).astype(int), np.floor((x - self.origin) / self.res).astype(int)

    def integrate(self, pose, angles, ranges, range_min, range_max):
        """pose = (x, y, yaw) of the scanner in the grid frame; rays with non-finite or out-of-range values are skipped."""
        px, py, yaw = pose
        ranges = np.asarray(ranges, float)
        ok = np.isfinite(ranges) & (ranges >= range_min) & (ranges <= range_max)
        if not ok.any():
            return
        theta = yaw + np.asarray(angles, float)[ok]
        r = ranges[ok]
        free_rows, free_cols = [], []
        step = self.res * 0.5
        for ray_r, ray_t in zip(r, theta):
            t = np.arange(0.0, ray_r - self.res, step)
            rows, cols = self._index(px + t * np.cos(ray_t), py + t * np.sin(ray_t))
            free_rows.append(rows)
            free_cols.append(cols)
        rows, cols = np.concatenate(free_rows), np.concatenate(free_cols)
        keep = (rows >= 0) & (rows < self.cells) & (cols >= 0) & (cols < self.cells)
        # a cell is updated once per scan no matter how many rays cross it
        free = np.unique(rows[keep] * self.cells + cols[keep])
        fr, fc = free // self.cells, free % self.cells
        self.log_odds[fr, fc] = np.maximum(self.l_min, self.log_odds[fr, fc] + self.l_free)
        self.touched[fr, fc] = True
        hr, hc = self._index(px + r * np.cos(theta), py + r * np.sin(theta))
        keep = (hr >= 0) & (hr < self.cells) & (hc >= 0) & (hc < self.cells)
        hit = np.unique(hr[keep] * self.cells + hc[keep])
        hr, hc = hit // self.cells, hit % self.cells
        self.log_odds[hr, hc] = np.minimum(self.l_max, self.log_odds[hr, hc] + self.l_hit + 0.4)  # cancels this scan's free update
        self.touched[hr, hc] = True

    def to_message_data(self, occupied=0.5, free=-0.5):
        """(data, origin_x, origin_y, width, height) cropped to the observed area; values 100 / 0 / -1."""
        if not self.touched.any():
            return None
        rows = np.where(self.touched.any(axis=1))[0]
        cols = np.where(self.touched.any(axis=0))[0]
        r0, r1, c0, c1 = max(rows[0] - 10, 0), min(rows[-1] + 11, self.cells), max(cols[0] - 10, 0), min(cols[-1] + 11, self.cells)
        sub = self.log_odds[r0:r1, c0:c1]
        seen = self.touched[r0:r1, c0:c1]
        data = np.full(sub.shape, -1, np.int8)
        data[seen & (sub < free)] = 0
        data[seen & (sub > occupied)] = 100
        return data.ravel(), self.origin + c0 * self.res, self.origin + r0 * self.res, c1 - c0, r1 - r0
