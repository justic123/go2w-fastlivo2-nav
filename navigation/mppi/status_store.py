"""Bounded RAM heartbeats; slow durable mirrors never run in ROS callbacks.

Readers retain the existing run/*.json paths and freshness/health checks. A
missing RAM store is an error, never a reason to fall back to an old archive.
"""
import json
import os
import threading
import time
from pathlib import Path

NAMES = ('input', 'runtime', 'localization', 'lifecycle')
MAX_BYTES = 65536
MIRROR_INTERVAL = 5.


def _base():
    return Path('/dev/shm') / ('go2w-nav-health-' + str(os.getuid()))


def _atomic(path, text):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def prepare(root):
    """Called before starting a new board container, never on an active run."""
    root = Path(root)
    base = _base()
    if base.parent == Path('/dev/shm'):
        mounts = [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
        if not any(len(row) > 2 and row[1:3] == ['/dev/shm', 'tmpfs'] for row in mounts):
            raise ValueError('Heartbeat store requires tmpfs')
    base.mkdir(mode=0o700, exist_ok=True)
    if base.is_symlink() or base.stat().st_uid != os.getuid():
        raise ValueError('Untrusted RAM status directory')
    memory = base / root.name
    memory.mkdir(mode=0o700)
    (root / 'health-archive').mkdir()
    for name in NAMES:
        (root / (name + '.json')).symlink_to(memory / (name + '.json'))
    _atomic(root / 'health-store.json', json.dumps(dict(version=1, directory=str(memory))))


class StatusWriter:
    def __init__(self, root, name):
        if name not in NAMES:
            raise ValueError('Unknown heartbeat')
        self.root = Path(root)
        self.path = self.root / (name + '.json')
        self.archive = None
        marker = self.root / 'health-store.json'
        if marker.exists():
            spec = json.loads(marker.read_text())
            memory = Path(spec['directory'])
            if spec.get('version') != 1 or memory.parent != _base() or not memory.is_dir() or memory.is_symlink():
                raise ValueError('RAM status store unavailable')
            expected = memory / self.path.name
            if not self.path.is_symlink() or Path(os.readlink(self.path)) != expected:
                raise ValueError('Heartbeat link does not match this run')
            self.path = expected
            self.archive = self.root / 'health-archive' / self.path.name
        self.condition = threading.Condition()
        self.latest = None
        self.closed = False
        self.thread = None
        if self.archive is not None:
            self.thread = threading.Thread(target=self._mirror, daemon=True)
            self.thread.start()

    def publish(self, data):
        text = json.dumps(data, allow_nan=False)
        if len(text.encode()) > MAX_BYTES:
            raise ValueError('Oversize heartbeat')
        # Atomic replacement must target RAM, not replace the run's symlink.
        _atomic(self.path, text)
        if self.archive is not None:
            with self.condition:
                self.latest = text  # One latest slot, no disk backlog queue.
                self.condition.notify()

    def _mirror(self):
        deadline = 0.
        while True:
            with self.condition:
                while not self.closed and (self.latest is None or time.monotonic() < deadline):
                    self.condition.wait(None if self.latest is None else max(0., deadline-time.monotonic()))
                if self.closed:
                    return
                text = self.latest
                self.latest = None
            try:
                _atomic(self.archive, text)
            except OSError:
                pass  # Archives never grant readiness; RAM write errors propagate.
            deadline = time.monotonic() + MIRROR_INTERVAL

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify()


_writers = {}


def publish(root, name, data):
    key = (str(root), name)
    if key not in _writers:
        _writers[key] = StatusWriter(root, name)
    _writers[key].publish(data)


def finalize(root):
    """After Docker has stopped, preserve final RAM snapshots in run history."""
    root = Path(root)
    marker = root / 'health-store.json'
    if not marker.exists():
        return
    spec = json.loads(marker.read_text())
    memory = Path(spec['directory'])
    if memory.parent != _base() or memory.is_symlink():
        raise ValueError('Untrusted RAM status directory')
    for name in NAMES:
        path = root / (name + '.json')
        source = memory / path.name
        if path.is_symlink() and Path(os.readlink(path)) == source:
            if source.exists():
                _atomic(path, source.read_text())
            else:
                path.unlink()  # Never invent a ready snapshot.
        if source.exists():
            source.unlink()
    if memory.exists():
        memory.rmdir()
