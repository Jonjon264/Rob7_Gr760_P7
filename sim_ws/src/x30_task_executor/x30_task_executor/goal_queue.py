"""Ordered goal queue with cancel-by-name, independent of ROS so it can be tested alone."""

from collections import deque


class GoalQueue:
    def __init__(self):
        self.pending = deque()
        self.active = None  # (goal_id, pose) currently handed to Nav2

    def replace(self, goals):
        """A new request supersedes everything queued; returns True if a goal was active."""
        self.pending = deque(goals)
        return self.active is not None

    def next(self):
        if self.active is None and self.pending:
            self.active = self.pending.popleft()
        return self.active

    def finish(self):
        self.active = None

    def cancel(self, name):
        """Cancel one named goal, or everything when name is empty.

        Returns (removed_pending, cancel_active).
        """
        if not name:
            removed = len(self.pending)
            self.pending.clear()
            return removed, self.active is not None
        kept = deque(g for g in self.pending if g[0] != name)
        removed = len(self.pending) - len(kept)
        self.pending = kept
        return removed, self.active is not None and self.active[0] == name
