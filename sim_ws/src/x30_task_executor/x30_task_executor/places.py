"""Read and edit the places file shared with the Qwen voice manager (map.json)."""

import json
import os
import tempfile
from pathlib import Path


def add_place(map_file, name, descriptor, x, y):
    """Add a place, replacing any existing place with the same name."""
    places = [p for p in _load(map_file) if p.get('name') != name]
    places.append({'x': round(x, 3), 'y': round(y, 3), 'name': name, 'descriptor': descriptor})
    _save(map_file, places)


def remove_place(map_file, name):
    """Remove every place with this name; returns how many were removed."""
    places = _load(map_file)
    kept = [p for p in places if p.get('name') != name]
    if len(kept) != len(places):
        _save(map_file, kept)
    return len(places) - len(kept)


def _load(map_file):
    return json.loads(Path(map_file).read_text(encoding='utf-8-sig'))


def _save(map_file, places):
    path = Path(map_file)
    # Write then rename so the voice manager never reads a half-written file.
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(places, handle, indent=4)
    os.replace(temp, path)
