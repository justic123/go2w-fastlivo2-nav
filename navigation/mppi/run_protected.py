"""Run a protected ROS action, then its requested arrival hook after guard shutdown."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from arrival_runner import finish
from motion_modes import arrival_motion, require_available


def run_action(args, root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    if not 10 <= args.timeout <= 1770:
        raise ValueError('timeout must be 10..1770 seconds')
    mode = '--execute' if args.execute else '--preview'
    state = Path(json.loads((root / 'current.json').read_text())['folder'])
    with (root / 'action.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = json.loads((state / 'accuracy_target.json').read_text())
        action = arrival_motion(target)
        # Preview only displays metadata. An unavailable requested operation
        # fails before navigation or robot participants are started.
        adapter = require_available([target]) if args.execute else None
        (state / 'arrival_cancel.request').unlink(missing_ok=True)
        started = time.time()
        result = None
        try:
            subprocess.run(['docker', 'exec', 'go2w-nav2-mppi', 'mkdir', '-p', '/tmp/mppi_policy'], check=True)
            for name in ('motion_policy.py', 'heading_guard.py', 'callback_drain.py'):
                subprocess.run(['docker', 'cp', str(root.parent / 'nav2' / name),
                                'go2w-nav2-mppi:/tmp/mppi_policy/' + name], check=True)
            guard = subprocess.Popen(['/usr/bin/python3', str(root / 'guard_server.py'),
                                      mode, '--timeout', str(args.timeout + 15)])
            try:
                end = time.monotonic() + 3
                while not (state / 'guard.sock').exists():
                    if guard.poll() is not None or time.monotonic() > end:
                        raise RuntimeError('Guard proxy startup failed')
                    time.sleep(.03)
                command = ['docker', 'exec', '-e', 'GO2W_GUARD_SOCKET=/state/guard.sock',
                           '-e', 'GO2W_ARRIVAL_ACTION_HOST=' + ('1' if args.execute and action['switch'] else '0'),
                           'go2w-nav2-mppi', 'bash', '-c',
                           'source /opt/ros/humble/setup.bash; exec python3 /work/execute.py "$@"',
                           '_', mode, '--timeout', str(args.timeout)]
                result = subprocess.run(command + (['--route'] if args.route else []))
            finally:
                subprocess.run(['docker', 'exec', 'go2w-nav2-mppi', 'pkill', '-INT', '-f',
                                '^python3 /work/execute.py'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    guard.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    guard.terminate()
                    guard.wait(timeout=5)
            # A mode request must not overlap an open velocity guard.
            if args.execute and action['switch'] and result.returncode == 0:
                (state / 'motion_active').write_text(json.dumps(dict(
                    execute=True, started=started, phase='arrival_motion', target=target['name'])))
                outcome = finish(state, target, adapter=adapter, started=started, route=args.route)
                print(json.dumps(dict(arrival_motion=outcome), ensure_ascii=False), flush=True)
        finally:
            if args.execute and action['switch']:
                (state / 'motion_active').unlink(missing_ok=True)
        return result.returncode if result is not None else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--route', action='store_true')
    return run_action(parser.parse_args())


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print('执行已停止：' + (str(error) or '用户取消'), file=sys.stderr)
        raise SystemExit(1)
