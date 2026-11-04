"""Prevent two launches from sharing one simulator's world files and topics."""
import fcntl
from pathlib import Path

_lock_file = None


def acquire_simulator_lock(work_dir):
    global _lock_file
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    handle = (work_dir / 'launch.lock').open('a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('A simulator is already running in this container. Stop the existing launch before starting another.') from None
    # Retain the descriptor until the launch process exits; the OS releases
    # the lock even when that process crashes, so no stale PID cleanup is needed.
    _lock_file = handle
