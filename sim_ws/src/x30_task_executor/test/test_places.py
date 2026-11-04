import json

from x30_task_executor import places


def test_add_replace_and_remove(tmp_path):
    map_file = tmp_path / 'map.json'
    map_file.write_text(json.dumps([{'x': 1, 'y': 2, 'name': 'Dock', 'descriptor': 'old'}]))
    places.add_place(map_file, 'Dock', 'new', 3.14159, 4.0)
    places.add_place(map_file, 'Lab', 'lab', 0.0, 1.0)
    data = json.loads(map_file.read_text())
    assert [p['name'] for p in data] == ['Dock', 'Lab']
    assert data[0] == {'x': 3.142, 'y': 4.0, 'name': 'Dock', 'descriptor': 'new'}
    assert places.remove_place(map_file, 'Dock') == 1
    assert places.remove_place(map_file, 'Dock') == 0
    assert [p['name'] for p in json.loads(map_file.read_text())] == ['Lab']
