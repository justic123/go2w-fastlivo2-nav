"""User-started stop-at-each-waypoint missions; all motion stays in protected executor."""
import copy,json,math,time,sys,hashlib,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'navigation/mppi'))
from route_model import route_spec
from motion_modes import action_label,require_available,point_fingerprint,manual_handoff
from preview_recovery import wait_healthy

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

def resume_context(c):
 """Read-only checkpoint validation. Never infer arrival from proximity."""
 d=c.state();request=route_spec(d);request['source_session']=d.get('session')
 progress=c.read(c.folder()/'route_progress.json')
 if progress.get('phase')!='stopped':raise RuntimeError('没有已停止的未完成路线')
 if progress.get('map_id')!=d.get('map_id') or progress.get('source_session')!=d.get('session'):raise RuntimeError('地图或定位会话已变化，请重新建立路线任务')
 names=[t['name'] for t in request['targets']]
 if progress.get('names')!=names:raise RuntimeError('路线顺序已变化，不能沿用旧进度')
 completed=progress.get('completed');results=progress.get('results',[])
 if type(completed) is not int or not 0<=completed<len(names):raise RuntimeError('没有剩余目标或进度无效')
 if len(results)!=completed or [r.get('name') for r in results]!=names[:completed]:raise RuntimeError('已完成点记录不一致，禁止跳过途经点')
 if progress.get('fingerprint'):
  if progress['fingerprint']!=request['fingerprint']:raise RuntimeError('路线或到点参数已变化，请重新建立路线任务')
 else:
  # Compatibility only with the original pre-execution request, never with a
  # later preview. This promotes old progress without guessing goal settings.
  path=c.folder()/'route_request.json';original=c.read(path)
  if path.stat().st_mtime>progress.get('updated',0) or original.get('fingerprint')!=request['fingerprint'] or original.get('source_session')!=request['source_session'] or original.get('map_id')!=request['map_id'] or original.get('targets')!=request['targets']:
   raise RuntimeError('旧任务缺少可核对的原路线快照，请重新建立路线任务')
 token=hashlib.sha256(json.dumps(dict(progress=progress,fingerprint=request['fingerprint']),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return request,progress,token

def resume_status(c):
 try:
  request,p,token=resume_context(c)
  return dict(available=True,token=token,completed=p['completed'],total=len(p['names']),remaining=p['names'][p['completed']:],reason=None)
 except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:return dict(available=False,reason=str(e))

def preview(c,resume=False,expected_token=None):
 c.assert_no_motion();c.check_session(c.state())
 wait_healthy(c.health,timeout=8.)
 full=spec(c);c.assert_no_motion();request=full
 c.save(route_preview=None,route_resume_preview=None)
 if resume:
  request,p,token=resume_context(c)
  if expected_token is not None and token!=expected_token:raise RuntimeError('停止任务进度已变化，请刷新后重新预演')
  if not p.get('fingerprint'):
   c.write(c.folder()/('route_progress-legacy-'+str(time.time_ns())+'.json'),p)
   p.update(fingerprint=full['fingerprint'],mission_id=uuid.uuid4().hex)
   c.write(c.folder()/'route_progress.json',p);c.write(c.MPPI/'maps'/full['map_id']/'mission_progress.json',p)
   request,p,token=resume_context(c)
  request=copy.deepcopy(request);request['targets']=request['targets'][p['completed']:]
  request['fingerprint']=hashlib.sha256((full['fingerprint']+':'+token).encode()).hexdigest()
 c.write(c.folder()/'route_request.json',request)
 started=time.time()
 try:
  c.run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/route_preview.py'],20*len(request['targets'])+15)
 except RuntimeError as error:
  try:failure=c.read(c.folder()/'route_preview.json')
  except (OSError,ValueError):failure={}
  if failure.get('fingerprint')==request['fingerprint'] and failure.get('source_session')==request['source_session'] and failure.get('created',0)>=started and failure.get('reason'):
   raise RuntimeError('预演未通过：'+failure['reason']) from error
  raise
 result=c.read(c.folder()/'route_preview.json')
 if not result.get('success') or result['fingerprint']!=request['fingerprint'] or result['source_session']!=request['source_session']:raise RuntimeError('路线预演未通过')
 if resume:
  result.update(resume_token=token,completed=p['completed'],full_fingerprint=full['fingerprint'])
  c.save(route_resume_preview=result)
 else:c.save(route_preview=result)
 c.write(c.MPPI/'maps'/request['map_id']/'mission_view.json',result)
 c.view('navigation')
 print(('剩余路线' if resume else '全路线')+'预演通过，长度 %.2f 米；60秒内可确认执行。每段实际运动前仍会重新规划。'%sum(s['length_m'] for s in result['segments']))

def close_to_start(c,start):
 p=c.current_map_pose()
 return math.dist(p[:2],start[:2])<=.05 and abs(math.atan2(math.sin(p[2]-start[2]),math.cos(p[2]-start[2])))<=.1

def execute(c,resume=False,expected_token=None):
 request=spec(c);d=c.state();preview=d.get('route_resume_preview' if resume else 'route_preview');c.assert_no_motion();offset=0;prior_progress=None
 if resume:
  request,prior_progress,token=resume_context(c);offset=prior_progress['completed']
  if expected_token is not None and token!=expected_token:raise RuntimeError('停止任务进度已变化，请重新预演')
  if not preview or preview.get('resume_token')!=token or preview.get('completed')!=offset or preview.get('full_fingerprint')!=request['fingerprint']:raise RuntimeError('请先预演剩余路线，不能沿用整条路线预演')
 expected_fingerprint=hashlib.sha256((request['fingerprint']+':'+token).encode()).hexdigest() if resume else request['fingerprint']
 if not preview or not preview.get('success') or preview['fingerprint']!=expected_fingerprint or preview['source_session']!=request['source_session'] or not 0<=time.time()-preview['created']<60:raise RuntimeError('请先对当前路线重新预演；预演60秒有效')
 if not close_to_start(c,preview['start']):raise RuntimeError('路线预演后实机已移动，请重新预演')
 # Validate every point before departing, rather than discovering an unavailable
 # mode switch after reaching the first obstacle.
 require_available(request['targets'][offset:])
 frozen=copy.deepcopy(request);folder=c.folder();cancel=folder/'route_cancel.request';active=folder/'route_active.json';cancel.unlink(missing_ok=True)
 progress=dict(mission_id=uuid.uuid4().hex,fingerprint=request['fingerprint'],map_id=request['map_id'],source_session=request['source_session'],names=[t['name'] for t in request['targets']],phase='countdown',completed=0,index=0,updated=time.time(),results=[])
 if resume:
  progress=copy.deepcopy(prior_progress);progress.update(phase='countdown',index=offset,resumes=prior_progress.get('resumes',0)+1);progress.pop('error',None);progress.pop('failed_result',None)
 def report():
  progress['updated']=time.time();c.write(folder/'route_progress.json',progress);c.write(c.MPPI/'maps'/request['map_id']/'mission_progress.json',progress)
 def check():
  if cancel.exists():raise RuntimeError('路线已取消，不再进入下一点')
  fresh=spec(c)
  if fresh['fingerprint']!=frozen['fingerprint'] or fresh['source_session']!=frozen['source_session']:raise RuntimeError('路线、地图或定位会话变化，停止任务')
 def countdown():
  print('将逐点运动；保留遥控接管，Ctrl+C取消整条路线。')
  for i in range(5,0,-1):check();print(i,flush=True);time.sleep(1)
 c.write(active,dict(started=time.time(),map_id=request['map_id']));c.save(route_preview=None,route_resume_preview=None,preview=None)
 try:
  old=folder/'route_progress.json'
  if not resume and old.exists():
   c.write(folder/('route_progress-history-'+str(time.time_ns())+'.json'),c.read(old))
  report();countdown()
  for index in range(offset,len(frozen['targets'])):
   target=frozen['targets'][index]
   check();progress.update(index=index,phase='navigating');report();c.choose(target['name'])
   timeout=preview['segments'][index-offset]['timeout_s'];before=time.time()
   print('前往第%d/%d点：%s，限时%d秒'%(index+1,len(frozen['targets']),target['name'],timeout),flush=True)
   print('该点停稳后：'+action_label(target),flush=True)
   def version(p):
    s=p.stat();return (s.st_ino,s.st_mtime_ns,s.st_size)
   prior_results={p.name:version(p) for p in folder.glob('protected-execute-*.json')}
   command_error=None
   try:c.run(['/usr/bin/python3','navigation/mppi/run_protected.py','--execute','--route','--timeout',str(timeout)],timeout+45)
   except RuntimeError as e:command_error=e
   fresh_results=[p for p in folder.glob('protected-execute-*.json') if prior_results.get(p.name)!=version(p)]
   if not fresh_results:raise RuntimeError(str(command_error) if command_error else '本段没有新执行结果，禁止复用上一轮到点记录')
   result=c.read(max(fresh_results,key=lambda p:(p.stat().st_mtime_ns,p.name)))
   if result['target']['name']!=target['name'] or result['target']['source_session']!=request['source_session']:raise RuntimeError('执行结果不属于当前目标或会话')
   if command_error or not result.get('success') or not result.get('stationary_after_stop'):
    progress['failed_result']=dict(name=target['name'],xy_error=result.get('estimated_xy_error'),yaw_error=result.get('estimated_yaw_error'),stationary=result.get('stationary_after_stop'),reason=result.get('reason') or str(command_error or '本点未到位并停稳'))
    raise RuntimeError('目标 '+target['name']+'：'+progress['failed_result']['reason'])
   if point_fingerprint(result['target'])!=point_fingerprint(d['points'][target['name']]):raise RuntimeError('到点记录的坐标、地图或动作参数不一致，不继续下一点')
   progress['results'].append(dict(name=target['name'],xy_error=result.get('estimated_xy_error'),yaw_error=result.get('estimated_yaw_error'),started=before));progress.update(completed=index+1,phase='dwelling');report()
   end=time.monotonic()+request['dwell_s']
   while time.monotonic()<end:check();time.sleep(.1)
  progress['phase']='awaiting_manual' if manual_handoff(frozen['targets'][-1]) else 'completed'
  report();print('已在接管点停稳并结束自动任务；请人工通过楼梯，在平台确认定位后另起平地任务。' if progress['phase']=='awaiting_manual' else '路线全部完成，已停稳。')
 except BaseException as e:
  progress.update(phase='stopped',error=str(e) or 'User interrupted');report();raise
 finally:
  active.unlink(missing_ok=True)
