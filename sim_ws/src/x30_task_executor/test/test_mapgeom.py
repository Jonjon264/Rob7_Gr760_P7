from x30_task_executor.mapgeom import MapGeometry


def make(tmp_path):
    (tmp_path / 'm.pgm').write_bytes(b'P5\n# comment\n40 20\n255\n' + bytes(800))
    (tmp_path / 'm.yaml').write_text('image: m.pgm\nresolution: 0.1\norigin: [-2.0, -1.0, 0]\nnegate: 0\n')
    return MapGeometry(tmp_path / 'm.yaml')


def test_size_and_corners(tmp_path):
    geom = make(tmp_path)
    assert (geom.width, geom.height) == (40, 20)
    x, y = geom.pixel_to_world(0, 19)          # bottom-left pixel is the origin cell
    assert abs(x - -1.95) < 1e-9 and abs(y - -0.95) < 1e-9
    x, y = geom.pixel_to_world(39, 0)          # top-right pixel
    assert abs(x - 1.95) < 1e-9 and abs(y - 0.95) < 1e-9


def test_roundtrip(tmp_path):
    geom = make(tmp_path)
    for px, py in [(0, 0), (13, 7), (39, 19)]:
        assert geom.world_to_pixel(*geom.pixel_to_world(px, py)) == (px, py)
