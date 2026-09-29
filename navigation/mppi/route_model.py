"""Map-bound stop-at-each-point missions. No ROS or robot commands."""
import hashlib,json,math

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
  targets.append(dict(name=name,pose=list(p)))
 d=dict(map_id=state['map_id'],targets=targets,mode='stop_at_each',dwell_s=2.)
 d['fingerprint']=hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest();return d

def leg_timeout(length):
 if not math.isfinite(length) or length<0:raise ValueError('Invalid planned length')
 seconds=max(90,math.ceil(30+length/.08))
 if seconds>1770:raise ValueError('单段路径所需时间超过上限，请增加中间停靠点')
 return seconds

def stationary(samples,span=1.5):
 if len(samples)<8:return False
 last=samples[-1];recent=[p for p in samples if last[3]-p[3]<=span]
 return len(recent)>=8 and recent[-1][3]-recent[0][3]>=span*.8 and all(math.hypot(p[0]-last[0],p[1]-last[1])<=.025 and abs(math.atan2(math.sin(p[2]-last[2]),math.cos(p[2]-last[2])))<=.025 for p in recent)
