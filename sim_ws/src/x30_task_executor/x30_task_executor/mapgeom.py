"""Convert between map-image pixels (as clicked in Map/Labeling.py) and metres in the map frame."""

from pathlib import Path


def _pgm_size(path):
    """(width, height) of a binary (P5) or ASCII (P2) PGM."""
    tokens, data = [], Path(path).read_bytes()
    for line in data.split(b'\n'):
        line = line.split(b'#')[0].strip()
        if line:
            tokens += line.split()
        if len(tokens) >= 3:
            break
    return int(tokens[1]), int(tokens[2])


class MapGeometry:
    def __init__(self, yaml_path):
        values = {}
        for line in Path(yaml_path).read_text().splitlines():
            if ':' in line and not line.lstrip().startswith('#'):
                key, value = line.split(':', 1)
                values[key.strip()] = value.strip()
        self.resolution = float(values['resolution'])
        origin = values['origin'].strip('[] ').split(',')
        self.origin_x, self.origin_y = float(origin[0]), float(origin[1])
        self.width, self.height = _pgm_size(Path(yaml_path).parent / values['image'].strip('"\''))

    def pixel_to_world(self, px, py):
        # image row 0 is the top (largest y); a pixel maps to the centre of its cell
        return (self.origin_x + (px + 0.5) * self.resolution,
                self.origin_y + (self.height - py - 0.5) * self.resolution)

    def world_to_pixel(self, x, y):
        return (round((x - self.origin_x) / self.resolution - 0.5),
                round(self.height - 0.5 - (y - self.origin_y) / self.resolution))
