from x30_task_executor.goal_queue import GoalQueue


def queue_with(*names):
    queue = GoalQueue()
    queue.replace([(n, object()) for n in names])
    return queue


def test_goals_run_in_order():
    queue = queue_with('a', 'b')
    assert queue.next()[0] == 'a'
    assert queue.next()[0] == 'a'  # still active until finished
    queue.finish()
    assert queue.next()[0] == 'b'
    queue.finish()
    assert queue.next() is None


def test_cancel_all_clears_queue_and_flags_active():
    queue = queue_with('a', 'b')
    queue.next()
    assert queue.cancel('') == (1, True)
    assert not queue.pending


def test_cancel_by_name():
    queue = queue_with('a', 'b', 'c')
    queue.next()
    assert queue.cancel('b') == (1, False)
    assert queue.cancel('a') == (0, True)
    assert [g[0] for g in queue.pending] == ['c']
    assert queue.cancel('unknown') == (0, False)


def test_new_request_replaces_queue():
    queue = queue_with('a', 'b')
    queue.next()
    assert queue.replace([('c', None)]) is True
    assert [g[0] for g in queue.pending] == ['c']
