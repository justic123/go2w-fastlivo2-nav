"""User-started stop-at-each-waypoint missions; all motion stays in protected executor."""
import copy,json,math,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'navigation/mppi'))
from route_model import route_spec

def spec(c):
 d=c.state();c.check_session(d);c.health()
 if d.get('phase')!='navigation':raise RuntimeError('请先恢复并验证地图定位')
 result=route_spec(d)
 for name in d['route']['names']:
  if d['points'][name]['source_session']!=d['session']:raise RuntimeError('目标尚未绑定当前定位会话')
 result['source_session']=d['session'];return result

def set_route(c,names=None):
 c.assert_no_motion();d=c.state()
 if names is None:
  print('已保存点：'+'、'.join(d.get('points',{})))
  names=input('按经过顺序输入点名，用逗号分隔（如 A,B,C,A；回车取消）：').strip()
 if not names:return
 ordered=[x.strip() for x in names.replace('，',',').split(',')];route_spec(d,ordered)
 c.save(route=dict(names=ordered,mode='stop_at_each'),route_preview=None)
 c.write(c.MPPI/'maps'/d['map_id']/'console_points.json',dict(points=d['points'],selected=d.get('selected'),route=c.state()['route']))
 print('路线：'+' → '.join(ordered)+'；每点达到位置和朝向、停稳后再继续。')

def preview(c):
 request=spec(c);c.assert_no_motion();c.save(route_preview=None)
 c.write(c.folder()/'route_request.json',request)
 c.run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/route_preview.py'],20*len(request['targets'])+15)
 result=c.read(c.folder()/'route_preview.json')
 if not result.get('success') or result['fingerprint']!=request['fingerprint'] or result['source_session']!=request['source_session']:raise RuntimeError('路线预演未通过')
 c.save(route_preview=result)
 c.write(c.MPPI/'maps'/request['map_id']/'mission_view.json',result)
 c.view('navigation')
 print('全路线预演通过，长度 %.2f 米；60秒内可选择16开始。每段实际运动前仍会重新规划。'%sum(s['length_m'] for s in result['segments']))

def close_to_start(c,start):
 p=c.current_map_pose()
 return math.dist(p[:2],start[:2])<=.05 and abs(math.atan2(math.sin(p[2]-start[2]),math.cos(p[2]-start[2])))<=.1

def execute(c):
 request=spec(c);d=c.state();preview=d.get('route_preview');c.assert_no_motion()
 if not preview or not preview.get('success') or preview['fingerprint']!=request['fingerprint'] or preview['source_session']!=request['source_session'] or not 0<=time.time()-preview['created']<60:raise RuntimeError('请先选15对当前路线重新预演；预演60秒有效')
 if not close_to_start(c,preview['start']):raise RuntimeError('路线预演后实机已移动，请重新预演')
 frozen=copy.deepcopy(request);folder=c.folder();cancel=folder/'route_cancel.request';active=folder/'route_active.json';cancel.unlink(missing_ok=True)
 progress=dict(map_id=request['map_id'],source_session=request['source_session'],names=[t['name'] for t in request['targets']],phase='countdown',completed=0,index=0,updated=time.time(),results=[])
 def report():
  progress['updated']=time.time();c.write(folder/'route_progress.json',progress);c.write(c.MPPI/'maps'/request['map_id']/'mission_progress.json',progress)
 def check():
  if cancel.exists():raise RuntimeError('路线已取消，不再进入下一点')
  fresh=spec(c)
  if fresh['fingerprint']!=frozen['fingerprint'] or fresh['source_session']!=frozen['source_session']:raise RuntimeError('路线、地图或定位会话变化，停止任务')
 def countdown():
  print('将逐点运动；保留遥控接管，Ctrl+C取消整条路线。')
  for i in range(5,0,-1):check();print(i,flush=True);time.sleep(1)
 c.write(active,dict(started=time.time(),map_id=request['map_id']));c.save(route_preview=None,preview=None)
 try:
  report();countdown()
  for index,target in enumerate(frozen['targets']):
   check();progress.update(index=index,phase='navigating');report();c.choose(target['name'])
   timeout=preview['segments'][index]['timeout_s'];before=time.time()
   print('前往第%d/%d点：%s，限时%d秒'%(index+1,len(frozen['targets']),target['name'],timeout),flush=True)
   c.run(['/usr/bin/python3','navigation/mppi/run_protected.py','--execute','--route','--timeout',str(timeout)],timeout+45)
   result=c.read(max(folder.glob('protected-execute-*.json'),key=lambda p:(p.stat().st_mtime_ns,p.name)))
   if not result.get('success') or not result.get('stationary_after_stop') or result['target']['name']!=target['name'] or result['target']['source_session']!=request['source_session']:raise RuntimeError('本点未到位并停稳，不继续下一点')
   progress['results'].append(dict(name=target['name'],xy_error=result.get('estimated_xy_error'),yaw_error=result.get('estimated_yaw_error'),started=before));progress.update(completed=index+1,phase='dwelling');report()
   end=time.monotonic()+request['dwell_s']
   while time.monotonic()<end:check();time.sleep(.1)
  progress['phase']='completed';report();print('路线全部完成，已停稳。')
 except BaseException as e:
  progress.update(phase='stopped',error=str(e) or 'User interrupted');report();raise
 finally:
  active.unlink(missing_ok=True)
