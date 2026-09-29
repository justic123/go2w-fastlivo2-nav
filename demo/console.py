#!/usr/bin/env python3
"""Chinese interactive demo console. Only the explicit navigate action enables motion."""
import argparse,fcntl,hashlib,json,math,os,select,shutil,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];MPPI=ROOT/'navigation/mppi';STATE=ROOT/'demo/state.json'

def read(p):return json.loads(Path(p).read_text())
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2));t.replace(p)
def state():return read(STATE) if STATE.exists() else dict(phase='idle',points={})
def save(**kw):
 d=state();d.update(kw);write(STATE,d)
def run(args,timeout=120):
 print('>> '+' '.join(map(str,args)),flush=True)
 p=subprocess.Popen(list(map(str,args)),cwd=ROOT,start_new_session=True)
 try:
  code=p.wait(timeout=timeout)
 except (KeyboardInterrupt,subprocess.TimeoutExpired):
  os.killpg(p.pid,signal.SIGINT)
  try:p.wait(timeout=12)
  except subprocess.TimeoutExpired:
   # Explicitly cancel the container action before ending a hung host command.
   stop_motion()
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:raise RuntimeError('子进程未退出，请检查日志，暂不允许启动下一次操作')
  raise RuntimeError('操作已取消；若为运动，请确认实机停稳')
 if code:raise RuntimeError('命令失败，已停止本步骤；请查看以上错误')
def current():return read(MPPI/'current.json')
def folder():return Path(current()['folder'])
def desk():return read(ROOT/'desktop/current.json')
def check_session(d):
 if desk()['run']!=d.get('session') or current()['session']!=d.get('session'):
  raise RuntimeError('融合会话已变化；请选择9或10恢复旧地图定位，原目标暂不可用')
def service_problem():
 if state().get('phase') in ('recovering','recovery_failed','map_selected','validating_map','starting'):return '地图定位尚未验证；请完成恢复流程'
 try:
  dc=desk();runtime=read(Path(dc['folder'])/'runtime.json')
  if runtime.get('phase')!='running':return '融合定位已停止：'+str(runtime.get('error') or runtime.get('phase'))
  h=read(Path(dc['folder'])/'health.json')
  if not h.get('ready') or not 0<=time.time()-h['updated']<2:return '融合定位数据过期/未就绪'
  r=folder();runtime=read(r/'runtime.json')
  if runtime.get('phase')!='running':return '导航服务已停止：'+str(runtime.get('error') or runtime.get('phase'))
  d=state()
  if d.get('phase')=='navigation':
   check_session(d);loc=read(r/'localization.json')
   if loc.get('map_id')!=d.get('map_id'):return '当前定位不是所选地图'
  health(d.get('phase')!='mapping')
  return None
 except (OSError,ValueError,KeyError,RuntimeError) as e:return str(e)
def health(selected=True):
 r=folder()
 for k in ['input','lifecycle']+(['localization'] if selected else []):
  d=read(r/(k+'.json'))
  if not d.get('ready') or not 0<=time.time()-d['updated']<1:raise RuntimeError(k+'未就绪/过期')
 d=read(r/'runtime.json')
 if d['phase']!='running' or not 0<=time.time()-d['updated']<1:raise RuntimeError('导航运行状态过期')
def wait_ready(selected):
 end=time.monotonic()+30
 while time.monotonic()<end:
  try:health(selected);return
  except (OSError,ValueError,RuntimeError):time.sleep(.5)
 raise RuntimeError('服务30秒内未就绪，请检查状态')
def stop_motion():
 try:
  if (folder()/'route_active.json').exists():(folder()/'route_cancel.request').touch()
 except (OSError,ValueError):pass
 # No SDK initialization: signal only our existing protected action.
 subprocess.run(['docker','exec','go2w-nav2-mppi','pkill','-INT','-f','^python3 /work/execute.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
 end=time.monotonic()+8
 while time.monotonic()<end:
  try:active=(folder()/'motion_active').exists()
  except (OSError,ValueError):active=False
  if not active:return
  time.sleep(.2)
 raise RuntimeError('导航取消尚未确认，请遥控接管；不要启动新任务')
def assert_no_motion():
 try:
  if (folder()/'motion_active').exists() or (folder()/'route_active.json').exists():raise RuntimeError('已有运动/路线任务，请先停止导航')
 except FileNotFoundError:pass

def archive_state():
 d=state()
 if d.get('map_id') and (MPPI/'maps'/d['map_id']).is_dir():write(MPPI/'maps'/d['map_id']/'console_points.json',dict(points=d.get('points',{}),selected=d.get('selected'),route=d.get('route')))
 dest=ROOT/'demo/backups'/str(time.time_ns());write(dest/'state.json',d)
 if (MPPI/'selection.json').exists():shutil.copy2(MPPI/'selection.json',dest/'selection.json')
 return dest

def validate_registration(candidate,ident,session):
 import numpy as np
 if candidate.get('map_id')!=ident or candidate.get('source_session')!=session:raise RuntimeError('重定位结果地图/会话不一致')
 if not candidate.get('accepted') or candidate.get('consensus',0)<3:raise RuntimeError('自动匹配未通过或存在歧义，保持停稳；不要启动导航')
 if not 0<=time.time()-candidate.get('created',0)<60:raise RuntimeError('重定位结果已过期')
 T=np.asarray(candidate['transform'],dtype=float)
 if T.shape!=(4,4) or not np.isfinite(T).all() or not np.allclose(T[3],[0,0,0,1]) or not np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-5) or not np.isclose(np.linalg.det(T[:3,:3]),1,atol=1e-5):raise RuntimeError('重定位变换无效')

def restore():
 # Keep map-frame goal coordinates. Never reuse the old camera_init transform.
 d=state();ident=d.get('map_id')
 if not ident or Path(ident).name!=ident or ident in ('.','..'):raise RuntimeError('没有可恢复的已保存地图')
 for name in ('map.yaml','map.pgm','points.npy'):
  if not (MPPI/'maps'/ident/name).is_file():raise RuntimeError('地图文件缺失：'+name)
 for target in d.get('points',{}).values():
  if target.get('map_id')!=ident or target.get('frame')!='map':raise RuntimeError('目标点不是当前保存地图的map坐标，禁止复用')
 assert_no_motion();archive_state();save(phase='recovering',preview=None)
 print('恢复地图 '+ident+'：请全程保持静止；不会发送运动指令。',flush=True)
 try:
  run(['bash','MPPI导航.sh','stop']);run(['/usr/bin/python3','desktop/control.py','stop'])
  if (MPPI/'selection.json').exists():(MPPI/'selection.json').unlink()
  run(['bash','重新采集.sh','restart']);run(['bash','本机建图测试.sh','start'])
  session=desk()['run']
  run(['/usr/bin/python3',MPPI/'make_config.py','--output',MPPI/'demo_nav.yaml'])
  run(['env','GO2W_MPPI_CONFIG=/work/demo_nav.yaml','bash','MPPI导航.sh','start']);wait_ready(False)
  run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/capture_local.py'],30)
  run(['docker','exec','go2w-nav2-mppi','python3','/work/relocalize.py','--map-id',ident],180)
  candidate=read(folder()/'registration_candidate.json');validate_registration(candidate,ident,session);health(False)
  activate_registration(d,candidate,session)
 except (Exception,KeyboardInterrupt) as e:
  save(phase='recovery_failed',preview=None,recovery_error=str(e) or '操作已取消');raise

def activate_registration(d,candidate,session):
 run(['bash','MPPI导航.sh','stop']);write(MPPI/'selection.json',candidate)
 run(['/usr/bin/python3',MPPI/'make_config.py','--output',MPPI/'demo_nav.yaml'])
 run(['env','GO2W_MPPI_CONFIG=/work/demo_nav.yaml','bash','MPPI导航.sh','start']);wait_ready(True)
 # Only rebind goals after the live scan-to-map validator accepts the transform.
 points=d.get('points',{})
 for target in points.values():
  target.setdefault('original_source_session',target['source_session']);target['source_session']=session
 save(phase='navigation',session=session,points=points,preview=None,route_preview=None,recovery_error=None)
 print('旧地图定位已恢复，原目标点已保留。先在RViz核对位置和机头方向，再选择4重新预演；不会自动导航。')

def prepare_assisted_inputs():
 # Reuse healthy FAST-LIVO2; only rebuild its session if fusion itself is down.
 assert_no_motion();archive_state();save(phase='recovering',preview=None,recovery_error=None)
 try:
  dc=desk();r=Path(dc['folder']);h=read(r/'health.json')
  fusion_ready=read(r/'runtime.json')['phase']=='running' and h.get('ready') and 0<=time.time()-h['updated']<2
 except (OSError,KeyError,ValueError):fusion_ready=False
 run(['bash','MPPI导航.sh','stop'])
 if (MPPI/'selection.json').exists():(MPPI/'selection.json').unlink()
 if not fusion_ready:
  run(['/usr/bin/python3','desktop/control.py','stop']);run(['bash','重新采集.sh','restart']);run(['bash','本机建图测试.sh','start'])
 run(['/usr/bin/python3',MPPI/'make_config.py','--output',MPPI/'demo_nav.yaml'])
 run(['env','GO2W_MPPI_CONFIG=/work/demo_nav.yaml','bash','MPPI导航.sh','start']);wait_ready(False)

def assisted_restore():
 d=state();ident=d.get('map_id')
 if not ident or d['phase'] in ('mapping','starting','validating_map'):raise RuntimeError('请先结束扫图并保存地图，再进行重定位')
 for filename in ('map.yaml','map.pgm','points.npy'):
  if not (MPPI/'maps'/ident/filename).is_file():raise RuntimeError('保存地图不完整')
 for target in d.get('points',{}).values():
  if target.get('map_id')!=ident or target.get('frame')!='map':raise RuntimeError('目标点不属于当前地图')
 try:prepare_assisted_inputs()
 except (Exception,KeyboardInterrupt) as e:
  save(phase='recovery_failed',preview=None,recovery_error=str(e) or '操作已取消');raise
 try:
  session=desk()['run']
  r=folder();hint=r/'initial_pose.json'
  if hint.exists():hint.unlink()
  # This read-only helper publishes the old map; it never publishes map->odom TF.
  subprocess.run(['docker','exec','go2w-nav2-mppi','pkill','-INT','-f','^python3 /work/initial_pose.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
  run(['docker','exec','-d','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/initial_pose.py --map-id "$1"','_',ident])
  view('navigation')
  print('保持静止。在导航RViz点击工具栏 2D Pose Estimate，在旧地图上按下当前位置，向机头方向拖动并松开。等待最多180秒；不会运动。',flush=True)
  deadline=time.monotonic()+180
  while not hint.exists():
   health(False)
   if time.monotonic()>deadline:raise RuntimeError('等待初始位置超时，请重试10')
   time.sleep(.2)
  save(phase='recovering',preview=None)
  run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/capture_local.py'],30)
  run(['docker','exec','go2w-nav2-mppi','python3','/work/relocalize.py','--map-id',ident,'--hint'],180)
  candidate=read(r/'registration_candidate.json');validate_registration(candidate,ident,session);health(False)
  activate_registration(d,candidate,session)
 except (Exception,KeyboardInterrupt) as e:
  save(phase='recovery_failed',preview=None,recovery_error=str(e) or '操作已取消');raise
 finally:
  subprocess.run(['docker','exec','go2w-nav2-mppi','pkill','-INT','-f','^python3 /work/initial_pose.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)

def start_mapping():
 assert_no_motion();archive_state();save(phase='starting',points={},preview=None,recovery_error=None,map_id=None,selected=None,session=None,route=None,route_preview=None)
 run(['bash','MPPI导航.sh','stop']);run(['/usr/bin/python3','desktop/control.py','stop'])
 if (MPPI/'selection.json').exists():
  dest=MPPI/'backups'/('console-'+str(time.time_ns()));dest.mkdir(parents=True);shutil.move(str(MPPI/'selection.json'),dest/'selection.json')
 # Reinitialize capture clock; never reuse a known old clock anchor for a new demo.
 run(['bash','重新采集.sh','restart']);run(['bash','本机建图测试.sh','start'])
 run(['/usr/bin/python3',MPPI/'make_config.py','--output',MPPI/'demo_nav.yaml']);run(['env','GO2W_MPPI_CONFIG=/work/demo_nav.yaml','bash','MPPI导航.sh','start']);wait_ready(False)
 session=desk()['run'];out=folder()/'demo-map'
 run(['docker','exec','-d','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/demo_collect.py'])
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  if (out/'status.json').exists():
   s=read(out/'status.json')
   if s['phase']=='failed':raise RuntimeError(s.get('error'))
   if s['frames']>=5:break
  time.sleep(.3)
 else:raise RuntimeError('地图采集器未收到点云')
 save(phase='mapping',session=session,points={},preview=None,map_id=None)
 print('扫图已开始：现在可遥控扫完整条路线。结束前请停稳；无3分钟限制。')

def finish_mapping():
 d=state()
 if d['phase']!='mapping':raise RuntimeError('当前不是扫图阶段')
 check_session(d);health(False)
 run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; python3 /work/demo_freeze.py'])
 old=folder();collect=old/'demo-map';(collect/'finish.request').touch()
 end=time.monotonic()+20
 while time.monotonic()<end:
  s=read(collect/'status.json')
  if s['phase']=='failed':raise RuntimeError(s.get('error'))
  if s['phase']=='saved':break
  time.sleep(.3)
 else:raise RuntimeError('三维地图保存超时')
 ident='demo-'+time.strftime('%Y%m%d-%H%M%S');dest=MPPI/'maps'/ident
 source=max(old.glob('frozen-map-*'),key=lambda p:p.stat().st_mtime)
 if read(source/'metadata.json')['session']!=d['session']:raise RuntimeError('地图会话不一致')
 shutil.copytree(source,dest);shutil.copy2(collect/'points.npy',dest/'points.npy')
 save(phase='validating_map',map_id=ident)
 run(['bash','MPPI导航.sh','stop'])
 write(MPPI/'selection.json',dict(map_id=ident,source_session=d['session'],created=time.time(),transform=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]],note='Map frozen in this live camera_init frame; validate before navigation'))
 run(['/usr/bin/python3',MPPI/'make_config.py','--output',MPPI/'demo_nav.yaml']);run(['env','GO2W_MPPI_CONFIG=/work/demo_nav.yaml','bash','MPPI导航.sh','start']);wait_ready(True)
 save(phase='navigation',preview=None,recovery_error=None)
 print('地图已保存并验证：'+ident+'。本轮地图采集已结束，FAST-LIVO2仍运行以提供定位。')

def record(name):
 d=state()
 if d['phase']!='navigation':raise RuntimeError('先结束扫图并验证地图')
 if not name.strip() or len(name)>64:raise RuntimeError('点名称需为1–64字符')
 check_session(d);health();run(['bash','MPPI导航.sh','record',name])
 target=read(folder()/'accuracy_target.json')
 if target['source_session']!=d['session'] or target['map_id']!=d['map_id']:raise RuntimeError('目标会话不一致')
 d['points'][name]=target;d['selected']=name;d['preview']=None;d['route_preview']=None;write(STATE,d);write(MPPI/'maps'/d['map_id']/'console_points.json',dict(points=d['points'],selected=name,route=d.get('route')));print('已保存当前位置和朝向：'+name)
def choose(name):
 d=state()
 if d['phase']!='navigation':raise RuntimeError('地图定位尚未恢复并验证')
 check_session(d);health()
 if name not in d['points']:raise RuntimeError('目标点不存在')
 t=d['points'][name]
 if t['source_session']!=d['session'] or t['map_id']!=d['map_id']:raise RuntimeError('旧目标不能用于当前地图')
 write(folder()/'accuracy_target.json',t);save(selected=name)
def preview(name):
 choose(name);save(preview=None);run(['bash','MPPI导航.sh','return-preview'],45)
 r=read(max(folder().glob('protected-preview-*.json'),key=lambda p:p.stat().st_mtime))
 if not r.get('preview_passed'):raise RuntimeError('预演未通过')
 save(preview=dict(name=name,at=time.time(),pose=r['last_pose'],timeout_s=r.get('recommended_timeout_s',90)))
 print('预演通过。请在RViz确认障碍被识别且路径从外侧绕行，再选择开始导航。')
def current_map_pose():
 import numpy as np
 r=folder();inp=read(r/'input.json');loc=read(r/'localization.json');v=inp['pose']['pose'];T=np.array(loc['transform']);xyz=T[:3,:3]@v[:3]+T[:3,3]
 x,y,z,w=v[3:];norm=x*x+y*y+z*z+w*w
 if not math.isfinite(norm) or abs(norm-1)>.02:raise RuntimeError('姿态四元数无效')
 forward=T[:3,:3]@np.array([1-2*(y*y+z*z)/norm,2*(x*y+w*z)/norm,2*(x*z-w*y)/norm]);return [float(xyz[0]),float(xyz[1]),math.atan2(forward[1],forward[0])]

def navigate(name):
 d=state()
 if d['phase']!='navigation':raise RuntimeError('地图定位尚未恢复并验证')
 check_session(d);health();p=d.get('preview')
 if not p or p['name']!=name or not 0<=time.time()-p['at']<60:raise RuntimeError('请先对该点预演，预演仅60秒内有效')
 xyz=current_map_pose();turn=math.atan2(math.sin(xyz[2]-p['pose'][2]),math.cos(xyz[2]-p['pose'][2]))
 if math.hypot(xyz[0]-p['pose'][0],xyz[1]-p['pose'][1])>.05 or abs(turn)>.1:raise RuntimeError('预演后位置/朝向变化，请重新预演')
 choose(name);save(preview=None)
 timeout_s=int(p.get('timeout_s',90));run(['bash','MPPI导航.sh','return-execute','--timeout',str(timeout_s)],timeout_s+45)
 print('任务结束，请确认实机停稳并测量。软件结果不能代替实测。')
def status():
 problem=service_problem();print('【禁止导航】'+problem if problem else '服务及定位就绪（运动仍需有效预演）')
 d=state();print(json.dumps(d,ensure_ascii=False,indent=2));run(['/usr/bin/python3','desktop/control.py','status']);run(['bash','MPPI导航.sh','status'])
def load_map(ident=None):
 maps=sorted(p.name for p in (MPPI/'maps').iterdir() if p.is_dir() and all((p/n).is_file() for n in ('map.yaml','map.pgm','points.npy')))
 print('已保存地图：\n'+'\n'.join(maps))
 ident=ident or input('输入要加载的完整地图名称（回车取消）：').strip()
 if not ident:return
 if ident not in maps:raise RuntimeError('地图不存在或文件不完整')
 assert_no_motion();archive_state()
 saved=MPPI/'maps'/ident/'console_points.json';points=read(saved) if saved.exists() else dict(points={})
 # Recover older named points saved before per-map storage was introduced.
 if not saved.exists():
  for p in sorted((ROOT/'demo/backups').glob('*/state.json'),reverse=True):
   old=read(p)
   if old.get('map_id')==ident:points=dict(points=old.get('points',{}),selected=old.get('selected'),route=old.get('route'));break
 run(['bash','MPPI导航.sh','stop'])
 save(phase='map_selected',map_id=ident,points=points['points'],selected=points.get('selected'),route=points.get('route'),route_preview=None,preview=None,recovery_error=None)
 view('navigation');print('底图和已保存目标已加载。选9自动或10辅助重定位；加载地图本身不等于定位成功。')

def record_map_point(name=None):
 d=state();ident=d.get('map_id');assert_no_motion()
 if not ident or d['phase'] in ('mapping','starting','validating_map'):raise RuntimeError('先保存或选择地图')
 name=name or input('新目标点名称：').strip()
 if not name or len(name)>64:raise RuntimeError('点名称需为1–64字符')
 view('navigation');began=time.time();deadline=time.monotonic()+180;p=MPPI/'maps'/ident/'clicked_goal.json'
 print('在导航RViz点击 2D Goal Pose，在目标位置按下并沿期望停靠朝向拖动。只保存目标，不会运动。',flush=True)
 while time.monotonic()<deadline:
  try:
   clicked=read(p)
   if clicked['map_id']==ident and clicked['created']>=began:break
  except (OSError,ValueError,KeyError):pass
  time.sleep(.2)
 else:raise RuntimeError('未收到目标点击，请重试17')
 target=dict(name=name,frame='map',map_id=ident,source_session=d.get('session'),pose=clicked['pose'],created=time.time(),source='rviz_map_click',ground_truth=None)
 d['points'][name]=target;d.update(selected=name,preview=None,route_preview=None);write(STATE,d)
 write(MPPI/'maps'/ident/'console_points.json',dict(points=d['points'],selected=name,route=d.get('route')))
 print('已保存地图目标：'+name+'。导航前必须完成定位和路径预演。')

def owned_process(pid,needle):
 try:return needle.encode() in (Path('/proc')/str(pid)/'cmdline').read_bytes()
 except OSError:return False

def saved_map_display():
 d=state();ident=d.get('map_id')
 if not ident:return
 pid=d.get('map_view_pid')
 digest=hashlib.sha256((MPPI/'initial_pose.py').read_bytes()).hexdigest()
 if pid and owned_process(pid,'initial_pose.py'):
  if d.get('map_view_id')==ident and d.get('map_view_hash')==digest:return
  os.kill(pid,signal.SIGTERM)
 env={k:v for k,v in os.environ.items() if k in ('HOME','USER','DISPLAY','XAUTHORITY')};env.update(PATH='/usr/bin:/bin',LANG='C.UTF-8')
 args=['bash','-c','source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=79 ROS_LOCALHOST_ONLY=1; exec /usr/bin/python3 "$1" --map-root "$2" --map-id "$3" --display-only','_',str(MPPI/'initial_pose.py'),str(MPPI/'maps'),ident]
 with (ROOT/'demo/map_view.log').open('a') as log:p=subprocess.Popen(args,env=env,stdout=log,stderr=log,start_new_session=True)
 save(map_view_pid=p.pid,map_view_id=ident,map_view_hash=digest)

def view(mode):
 if mode=='mapping':run(['bash','desktop/open_view.sh']);return
 saved_map_display()
 config=MPPI/('view_mapping.rviz' if state().get('phase')=='mapping' else 'view_cloud.rviz' if mode=='cloud' else 'view.rviz')
 context=dict(map_id=state().get('map_id'),phase=state().get('phase'),session=state().get('session'))
 try:context['live_session']=current().get('session');context['runtime_phase']=read(folder()/'runtime.json').get('phase')
 except (OSError,ValueError,KeyError):pass
 fingerprint=hashlib.sha256(config.read_bytes()+json.dumps(context,sort_keys=True).encode()).hexdigest()
 d=state();pid=d.get('rviz_pid')
 if pid and owned_process(pid,str(MPPI)) and owned_process(pid,'rviz2'):
  if d.get('rviz_config_hash')==fingerprint:print('对应导航RViz已打开');return
  os.kill(pid,signal.SIGTERM)
 with (ROOT/'demo/rviz.log').open('a') as log:
  p=subprocess.Popen(['bash','MPPI导航.sh','rviz',str(config)],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
 save(rviz_pid=p.pid,rviz_config_hash=fingerprint)
 print('二维导航窗口：灰度膨胀图＋点云＋路径＋机头箭头；局部膨胀和车身轮廓可在左侧勾选。' if mode!='cloud' else '三维点云窗口：可切回菜单7查看二维膨胀图。')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='menu',choices=['menu','status','start','finish','restore','assist','record','preview','navigate','stop','rviz','cloud','mapping-view','load-map','route-set','route-preview','route-execute','map-point']);parser.add_argument('name',nargs='?');args=parser.parse_args()
 if args.action=='stop':stop_motion();print('已请求取消导航；请确认实机停稳');return
 lock=(ROOT/'demo/console.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def dispatch(action,name=None):
  if action=='start':start_mapping()
  elif action=='finish':finish_mapping()
  elif action=='restore':
   if input('请确认正常站立并保持静止，输入“已停稳”恢复旧地图定位：').strip()!='已停稳':raise RuntimeError('未确认停稳，未启动恢复')
   restore()
  elif action=='assist':
   if input('保持静止，输入“已停稳”进入RViz辅助重定位：').strip()!='已停稳':raise RuntimeError('未确认停稳')
   assisted_restore()
  elif action=='record':record(name or input('目标点名称：').strip())
  elif action in ('preview','navigate'):
   print('已保存点：'+'、'.join(state().get('points',{})));n=name or input('选择点名称：').strip()
   (preview if action=='preview' else navigate)(n)
  elif action=='stop':stop_motion()
  elif action=='rviz':view('navigation')
  elif action=='cloud':view('cloud')
  elif action=='mapping-view':view('mapping')
  elif action=='load-map':load_map(name)
  elif action=='map-point':record_map_point(name)
  elif action.startswith('route-'):
   import mission
   c=sys.modules[__name__]
   if action=='route-set':mission.set_route(c,name)
   elif action=='route-preview':mission.preview(c)
   else:mission.execute(c)
  else:status()
 if args.action!='menu':dispatch(args.action,args.name);return
 while True:
  d=state();label={'idle':'未开始','starting':'正在初始化','mapping':'扫图中','validating_map':'存图校验中','navigation':'地图已保存（以实时状态为准）','map_selected':'已选旧地图，待重定位','recovering':'正在恢复旧地图定位','recovery_failed':'重定位未完成'}.get(d['phase'],d['phase'])
  print('\n=== Go2W 演示控制台 ===  '+label)
  print('地图：'+str(d.get('map_id') or '未保存')+' | 目标：'+'、'.join(d.get('points',{})))
  if d.get('route'):print('路线：'+' → '.join(d['route']['names']))
  if d.get('recovery_error') and d['phase']=='recovery_failed':print('恢复失败：'+d['recovery_error']+'；可选10辅助定位')
  if d['phase']!='idle':
   problem=service_problem()
   print('【禁止导航】'+problem if problem else '实时定位/服务正常')
  pv=d.get('preview');remaining=max(0,60-int(time.time()-pv['at'])) if pv else 0
  print(('预演有效：'+pv['name']+'，剩余'+str(remaining)+'秒') if remaining else '无有效预演；RViz中保留的路径不代表已允许运动')
  print('1 开始新扫图（先静止）\n2 结束扫图并保存（先停稳）\n3 保存当前位置为目标点\n4 选择点并预览路径（不运动）\n5 开始导航（会运动，Ctrl+C取消）\n6 停止导航\n7 打开二维导航RViz（膨胀图）\n8 查看状态及已保存点\n9 恢复当前保存地图的定位（先停稳，保留目标点）\n10 在RViz指定大致位置重定位（可直接使用，先静止）\n11 打开彩色建图窗口\n12 打开导航三维点云窗口\n13 选择已保存地图（保留对应目标）\n14 编辑逐点停靠路线\n15 预演整条路线（不运动）\n16 执行整条路线（逐点停稳）\n17 在RViz中添加地图目标（不运动）\n0 退出菜单（定位继续运行）')
  try:
   print('请选择：',end='',flush=True);previous=service_problem()
   while not select.select([sys.stdin],[],[],1)[0]:
    problem=service_problem()
    if problem!=previous:
     print('\n实时状态：'+(problem or '定位服务正常')+'\n请选择：',end='',flush=True);previous=problem
   choice=sys.stdin.readline()
   if not choice:break
   choice=choice.strip()
  except (EOFError,KeyboardInterrupt):break
  if choice=='0':break
  action={'1':'start','2':'finish','3':'record','4':'preview','5':'navigate','6':'stop','7':'rviz','8':'status','9':'restore','10':'assist','11':'mapping-view','12':'cloud','13':'load-map','14':'route-set','15':'route-preview','16':'route-execute','17':'map-point'}.get(choice)
  if not action:print('请输入菜单中的编号');continue
  try:dispatch(action)
  except Exception as e:print('未完成：'+str(e))
if __name__=='__main__':
 try:main()
 except (Exception,KeyboardInterrupt) as e:print('未完成：'+str(e),file=sys.stderr);sys.exit(1)
