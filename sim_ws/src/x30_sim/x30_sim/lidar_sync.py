"""Bounded timestamp buffering for LiDAR messages arriving in different orders.

Keep each sensor's scans until its peers arrive. A timeout emits only the
messages matching the oldest timestamp, leaving newer scans queued.
"""
from collections import deque
from typing import Any


class CloudSynchronizer:
    def __init__(self, keys, tolerance: float, timeout: float, max_queue: int = 8):
        if not keys or tolerance < 0 or timeout <= 0 or max_queue < 1:
            raise ValueError('synchronizer requires sensors and valid timing/buffer limits')
        self.queues = {key: deque() for key in keys}
        self.tolerance = tolerance
        self.timeout = timeout
        self.max_queue = max_queue
        self.last_stamp = float('-inf')
        self.dropped = 0

    def add(self, key: str, stamp: float, cloud: Any) -> None:
        # A late message for an already published partial scan cannot be reused.
        if stamp <= self.last_stamp + self.tolerance + 1e-9:
            self.dropped += 1
            return
        queue = self.queues[key]
        if len(queue) == self.max_queue:
            queue.popleft()
            self.dropped += 1
        queue.append((stamp, cloud))

    def pop_ready(self, now: float) -> dict[str, Any] | None:
        stamps = [queue[0][0] for queue in self.queues.values() if queue]
        if not stamps:
            return None
        oldest = min(stamps)
        matching = [key for key, queue in self.queues.items()
                    if queue and queue[0][0] - oldest <= self.tolerance + 1e-9]
        if len(matching) < len(self.queues) and now - oldest < self.timeout:
            return None
        scan = {key: self.queues[key].popleft()[1] for key in matching}
        self.last_stamp = oldest
        return scan
