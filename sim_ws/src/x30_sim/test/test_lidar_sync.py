"""Regression checks for staggered LiDAR delivery and missing scans."""
from x30_sim.lidar_sync import CloudSynchronizer


KEYS = ('fl', 'fr', 'rl', 'rr')


def test_delayed_sensor_preserves_earlier_matching_scan():
    sync = CloudSynchronizer(KEYS, tolerance=0.02, timeout=0.25)
    for stamp in (1.0, 1.1):
        for key in KEYS[:-1]:
            sync.add(key, stamp, (key, stamp))
        assert sync.pop_ready(1.12) is None
    sync.add('rr', 1.0, ('rr', 1.0))
    assert sync.pop_ready(1.12) == {key: (key, 1.0) for key in KEYS}
    sync.add('rr', 1.1, ('rr', 1.1))
    assert sync.pop_ready(1.13) == {key: (key, 1.1) for key in KEYS}
    assert sync.pop_ready(1.2) is None


def test_timeout_does_not_mix_different_scan_times():
    sync = CloudSynchronizer(KEYS, tolerance=0.02, timeout=0.25)
    for key in KEYS[:-1]:
        sync.add(key, 1.0, (key, 1.0))
    sync.add('rr', 1.1, ('rr', 1.1))
    assert sync.pop_ready(1.2) is None
    assert sync.pop_ready(1.3) == {key: (key, 1.0) for key in KEYS[:-1]}
    # The newer rr cloud is retained for the next complete scan.
    for key in KEYS[:-1]:
        sync.add(key, 1.1, (key, 1.1))
    assert sync.pop_ready(1.3) == {key: (key, 1.1) for key in KEYS}


def test_late_message_cannot_publish_an_old_scan_twice():
    sync = CloudSynchronizer(KEYS, tolerance=0.02, timeout=0.25)
    for key in KEYS[:-1]:
        sync.add(key, 1.0, key)
    assert sync.pop_ready(1.3) is not None
    sync.add('rr', 1.0, 'late')
    assert sync.pop_ready(2.0) is None


def test_timestamp_tolerance_includes_floating_point_boundary():
    sync = CloudSynchronizer(KEYS, tolerance=0.02, timeout=0.25)
    for key, stamp in zip(KEYS, (1.0, 1.005, 1.01, 1.02)):
        sync.add(key, stamp, key)
    assert sync.pop_ready(1.02) == {key: key for key in KEYS}


def test_absent_sensor_does_not_grow_buffers_without_limit():
    sync = CloudSynchronizer(KEYS, tolerance=0.02, timeout=0.25, max_queue=3)
    for stamp in (1.0, 1.1, 1.2, 1.3, 1.4):
        sync.add('fl', stamp, stamp)
    assert sync.pop_ready(2.0) == {'fl': 1.2}
    assert sync.pop_ready(2.0) == {'fl': 1.3}
    assert sync.pop_ready(2.0) == {'fl': 1.4}
    assert sync.pop_ready(2.0) is None
