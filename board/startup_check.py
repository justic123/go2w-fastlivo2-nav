"""Read-only launch diagnostics. Never stops owners or acquires sensor ports."""
import json
from pathlib import Path

SENSOR_NAMES={'xt16_driver','unitree_slam','fastlio_mapping','fastlivo_mapping'}


def read(path):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return {}


def process(path):
    try:
        fields=(path/'stat').read_text().rsplit(')',1)[1].split()
        if fields[0]=='Z':return None
        command=(path/'cmdline').read_bytes().split(b'\0')[0].decode()
        return dict(pid=int(path.name),parent=int(fields[1]),birth=fields[19],name=Path(command).name)
    except (OSError,ValueError,IndexError,UnicodeError):return None


def external_owners(project,proc=Path('/proc')):
    project=Path(project)
    if read(project/'board/deployment.json').get('backend')!='board':return []
    records={}
    for path in proc.iterdir():
        if path.name.isdigit():
            item=process(path)
            if item:records[item['pid']]=item
    current=read(project/'board/current.json');supervisor=current.get('pid')
    own=records.get(supervisor)
    owner=supervisor if own and own['birth']==current.get('birth') else None
    def ours(item):
        seen=set();pid=item['pid']
        while pid in records and pid not in seen:
            if pid==owner:return True
            seen.add(pid);pid=records[pid]['parent']
        return False
    return [item for item in records.values() if item['name'] in SENSOR_NAMES and not ours(item)]


def problem(project,proc=Path('/proc')):
    owners=external_owners(project,proc)
    if not owners:return None
    names='、'.join(item['name']+'（PID '+str(item['pid'])+'）' for item in owners)
    return '传感器被其他建图程序占用：'+names+'。请先正常结束这些程序，再重新开始扫图；网页不会自动停止它们。'


def describe(error):
    message=str(error or '')
    if 'External sensor/fusion owner PID ' in message:
        pid=message.rsplit('PID ',1)[-1]
        return '传感器被其他建图程序占用（PID '+pid+'）；请先正常结束原厂雷达/SLAM，再重新开始。'
    if 'Need 5 GiB free' in message:return '板端可用空间不足5GiB，融合未启动；请先归档录包释放空间。'
    return '板载融合启动失败：'+message
