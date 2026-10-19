"""Resolve fusion ownership explicitly; a desktop checkout stays on desktop."""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def onboard(project=PROJECT):
    marker = Path(project) / 'board/deployment.json'
    return marker.is_file() and json.loads(marker.read_text()).get('backend') == 'board'


def control(project=PROJECT):
    return Path(project) / ('board/control.py' if onboard(project) else 'desktop/control.py')


def current(project=PROJECT):
    return json.loads((control(project).parent / 'current.json').read_text())


def guard_command(execute, project=PROJECT):
    if onboard(project):
        # The same lease/watchdog as the desktop version, with no SSH-to-self.
        return ['/usr/bin/python3', str(Path(project) / 'navigation/mppi/guard/relay.py'),
                'execute' if execute else 'preview']
    return ['ssh', '-S', str(Path.home() / '.ssh/go2w-mapping.sock'), '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=4', 'unitree@192.168.123.18', 'python3',
            '/home/unitree/fast_livo2_port/build1/navigation/mppi_guard/relay.py',
            'execute' if execute else 'preview']
