"""Connect the GUI only once the server publishes the spawned robot's scene."""
import argparse
import os
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                ['gz', 'service', '-s', f'/world/{args.world}/scene/info',
                 '--reqtype', 'gz.msgs.Empty', '--reptype', 'gz.msgs.Scene',
                 '--timeout', '3000', '--req', ''],
                capture_output=True, text=True, timeout=5.0)
            if result.returncode == 0 and f'name: "{args.model}"' in result.stdout:
                # The server can publish its scene before the sensor renderer
                # completes the update that announces the new visuals.
                time.sleep(2.0)
                os.execvp('gz', ['gz', 'sim', '-g', '--gui-config', args.config])
        except subprocess.TimeoutExpired:
            pass
        time.sleep(0.5)
    raise RuntimeError(f'Gazebo did not publish model {args.model} in world {args.world}')


if __name__ == '__main__':
    main()
