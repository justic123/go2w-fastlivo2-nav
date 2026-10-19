"""Map-bound stop-at-each-point missions. No ROS or robot commands."""
import hashlib,json,math
from motion_modes import arrival_motion,manual_handoff

def route_spec(state,names=None):
 names=names if names is not None else (state.get('route') or {}).get('names',[])
 if not 2<=len(names)<=50:raise ValueError('路线需要2至50个有序目标点')
 targets=[]
 for name in names:
  if name not in state.get('points',{}):raise ValueError('目标不存在：'+name)
  t=state['points'][name]
  if t.get('frame')!='map' or t.get('map_id')!=state['map_id']:raise ValueError('目标地图不一致：'+name)
  p=t['pose']
  if len(p)!=3 or not all(math.isfinite(x) for x in p):raise ValueError('目标坐标无效')
  handoff=manual_handoff(t)
  if handoff and len(targets)!=len(names)-1:raise ValueError('人工接管点必须是本段路线最后一点；楼梯后请另建平地任务')
  targets.append(dict(name=name,pose=list(p),arrival_motion=arrival_motion(t),manual_handoff=handoff))
 d=dict(map_id=state['map_id'],targets=targets,mode='stop_at_each',dwell_s=2.)
 d['fingerprint']=hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest();return d

def leg_timeout(length):
 if not math.isfinite(length) or length<0:raise ValueError('Invalid planned length')
 seconds=max(90,math.ceil(30+length/.08))
 if seconds>1770:raise ValueError('单段路径所需时间超过上限，请增加中间停靠点')
 return seconds

def stationary(samples,span=1.5):
 from arrival_check import stationary_report
 return stationary_report(samples,span)['stationary']
