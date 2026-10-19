"""Attach only this action's Nav2 errors to an aborted navigation result."""
from pathlib import Path

LOGS = ('bt_navigator.log', 'controller_server.log', 'planner_server.log')


def checkpoint(folder):
    result = {}
    for name in LOGS:
        path = Path(folder) / name
        if path.exists():
            stat = path.stat()
            result[name] = (stat.st_ino, stat.st_size)
    return result


def failure_details(folder, before):
    details = []
    for name in LOGS:
        path = Path(folder) / name
        try:
            stat = path.stat()
            inode, offset = before.get(name, (None, 0))
            if stat.st_ino != inode or stat.st_size < offset:
                offset = 0
            with path.open('rb') as stream:
                stream.seek(max(offset, stat.st_size - 32768))
                lines = stream.read().decode('utf-8', errors='replace').splitlines()
            for line in lines:
                if '[ERROR]' in line or 'Timed out while waiting for action server' in line:
                    details.append(dict(log=name, message=line[-1500:]))
        except OSError:
            continue
    return details[-8:]


def abort_reason(status, details):
    for item in details:
        if 'Timed out while waiting for action server to acknowledge goal request' in item['message']:
            return '导航内部服务确认超时（不是无路径）：' + item['message']
    return 'Nav2 action ended with status ' + str(status) + (
        '; ' + details[-1]['message'] if details else '; inspect controller/planner logs')
