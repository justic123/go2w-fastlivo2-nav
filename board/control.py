#!/usr/bin/env python3
"""Native onboard FAST-LIVO lifecycle. Never starts navigation or motion."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'current.json'


def read(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def birth(pid):
    try:
        parts = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return parts[19] if parts[0] != 'Z' else None
    except (FileNotFoundError, ProcessLookupError):
        return None


def snapshot():
    d = read(STATE)
    d['running'] = bool(d.get('pid') and birth(d['pid']) == d.get('birth'))
    folder = Path(d.get('folder', '/nonexistent'))
    for key in ('runtime', 'health'):
        d[key] = read(folder / (key + '.json'))
    d['ready'] = bool(d['running'] and d['runtime'].get('phase') == 'running' and
                      d['health'].get('ready') and 0 <= time.time() - d['health'].get('updated', 0) < 2)
    d['compute_location'] = 'board'
    return d


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'status':
        print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
        return
    with (ROOT / 'control.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        d = snapshot()
        if action == 'start':
            if time.time() < 1704067200:
                raise RuntimeError('板端日期早于2024年；请先停止传感器并校正系统时间和RTC，不启动新地图')
            if not d['running']:
                if not (ROOT / 'deployment.json').is_file():
                    raise RuntimeError('No installed onboard deployment.json')
                run = 'board-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid())
                folder = ROOT / 'runs' / run
                folder.mkdir(parents=True)
                # A POSIX session does not escape systemd's web-service cgroup.
                # Own fusion in a separate transient unit so web restarts cannot kill it.
                if os.geteuid() == 0 and Path('/run/systemd/system').exists():
                    unit = 'go2w-fusion-' + run
                    command = ['systemd-run', '--quiet', '--unit=' + unit,
                               '--property=WorkingDirectory=' + str(ROOT.parent),
                               '--property=StandardOutput=append:' + str(folder / 'supervisor.log'),
                               '--property=StandardError=append:' + str(folder / 'supervisor.log'),
                               '--property=TimeoutStopSec=60', '--property=KillMode=mixed']
                    for key, value in os.environ.items():
                        if key.startswith(('GO2W_', 'OMP_', 'OPENBLAS_')) or key in ('HOME','PATH','LANG'):
                            command.append('--setenv=' + key + '=' + value)
                    subprocess.run(command + ['/usr/bin/python3', str(ROOT / 'runtime.py'), run], check=True)
                    pid = int(subprocess.check_output(['systemctl','show',unit,'--property=MainPID','--value'], text=True).strip())
                    if not pid or not birth(pid):raise RuntimeError('Independent fusion service failed to start')
                else:
                    with (folder / 'supervisor.log').open('w') as log:
                        p = subprocess.Popen(['/usr/bin/python3', str(ROOT / 'runtime.py'), run],
                                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                             start_new_session=True)
                    pid = p.pid
                STATE.write_text(json.dumps(dict(run=run, folder=str(folder), pid=pid, birth=birth(pid))))
            end = time.monotonic() + 45
            while time.monotonic() < end:
                d = snapshot()
                if d['ready']:
                    print(json.dumps(d, ensure_ascii=False));return
                if not d['running'] or d['runtime'].get('phase') == 'failed':
                    raise RuntimeError('Board initialization failed: ' + str(d))
                time.sleep(.2)
            raise RuntimeError('Initialization not ready after 45s; inspect status before moving')
        elif action == 'stop':
            nav = read(ROOT.parent / 'navigation/mppi/current.json')
            for marker in ('motion_active', 'route_active.json'):
                if (Path(nav.get('folder', '/nonexistent')) / marker).exists():
                    raise RuntimeError('Stop navigation before stopping fusion')
            if d['running']:
                os.kill(d['pid'], signal.SIGTERM)
                end = time.monotonic() + 45
                while snapshot()['running'] and time.monotonic() < end:time.sleep(.2)
                if snapshot()['running']:raise RuntimeError('Still closing owned children; do not force kill the bag')
            print('板载融合已停止；地图、日志保留。')
        else:
            raise RuntimeError('start/stop/status')


if __name__ == '__main__':
    try:main()
    except Exception as e:raise SystemExit(str(e))
