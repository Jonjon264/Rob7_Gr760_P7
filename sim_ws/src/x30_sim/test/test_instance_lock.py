"""A second simulator must fail before it can publish conflicting clocks."""
import os
import subprocess
import sys


def test_second_launch_is_rejected_and_exit_releases_lock(tmp_path):
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(sys.path)}
    code = ('from x30_sim.instance_lock import acquire_simulator_lock; '
            'import sys; acquire_simulator_lock(sys.argv[1])')
    first = subprocess.Popen([sys.executable, '-c', code + '; print("ready", flush=True); input()', str(tmp_path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert first.stdout.readline().strip() == 'ready'
        second = subprocess.run([sys.executable, '-c', code, str(tmp_path)], capture_output=True, text=True, env=env, timeout=5)
        assert second.returncode != 0
        assert 'already running' in second.stderr
    finally:
        first.communicate('\n', timeout=5)
    third = subprocess.run([sys.executable, '-c', code, str(tmp_path)], capture_output=True, text=True, env=env, timeout=5)
    assert third.returncode == 0, third.stderr
