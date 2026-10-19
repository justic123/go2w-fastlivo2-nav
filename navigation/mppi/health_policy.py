"""Shared fail-closed context checks for velocity execution and arrival actions."""
import json,math,time
from pathlib import Path

class ContextError(RuntimeError):
    def __init__(self,message,docs,now):
        super().__init__(message)
        self.snapshot=dict(captured=now,documents=docs)


def check_context(root,target,max_age,now=None):
    root=Path(root)
    if not target.get('map_id') or not target.get('source_session'):raise RuntimeError('目标缺少地图或会话标识')
    docs={k:json.loads((root/(k+'.json')).read_text()) for k in ('input','localization','lifecycle','runtime')}
    now=time.time() if now is None else now
    def failure(message):return ContextError(message,docs,now)
    for k,d in docs.items():
        stamp=d.get('updated')
        if type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0<=now-stamp<1:
            raise failure(k+'状态过期或时钟异常')
        if (k=='runtime' and d.get('phase')!='running') or (k!='runtime' and not d.get('ready')):
            raise failure(k+'未就绪')
    d=docs['input'];l=docs['localization']
    if d.get('fault') or d.get('session')!=target.get('source_session'):raise failure('输入故障或会话变化')
    if l.get('map_id')!=target.get('map_id') or l.get('source_session')!=target.get('source_session'):raise failure('地图或定位会话变化')
    for k in ('pose_age_s','cloud_age_s'):
        age=d.get(k)
        if type(age) not in (int,float) or not math.isfinite(age) or not -.05<=age<=max_age:raise failure('传感器延迟或时间异常: %s=%r s (上限 %.3f s)'%(k,age,max_age))
    return docs
