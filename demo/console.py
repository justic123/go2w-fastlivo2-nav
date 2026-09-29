#!/usr/bin/env python3
"""Chinese interactive demo console. Only the explicit navigate action enables motion."""
import argparse,fcntl,json,math,os,shutil,signal,subprocess,sys,time
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
  raise RuntimeError('融合会话已变化，旧点失效；请重新开始扫图')
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
  if (folder()/'motion_active').exists():raise RuntimeError('已有运动任务，请先停止导航')
 except FileNotFoundError:pass

def start_mapping():
 assert_no_motion();save(phase='starting',points={},preview=None)
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
 save(phase='navigation',preview=None)
 print('地图已保存并验证：'+ident+'。本轮地图采集已结束，FAST-LIVO2仍运行以提供定位。')

def record(name):
 d=state()
 if d['phase']!='navigation':raise RuntimeError('先结束扫图并验证地图')
 if not name.strip() or len(name)>64:raise RuntimeError('点名称需为1–64字符')
 check_session(d);health();run(['bash','MPPI导航.sh','record',name])
 target=read(folder()/'accuracy_target.json')
 if target['source_session']!=d['session'] or target['map_id']!=d['map_id']:raise RuntimeError('目标会话不一致')
 d['points'][name]=target;d['selected']=name;d['preview']=None;write(STATE,d);print('已保存当前位置和朝向：'+name)
def choose(name):
 d=state();check_session(d);health()
 if name not in d['points']:raise RuntimeError('目标点不存在')
 t=d['points'][name]
 if t['source_session']!=d['session'] or t['map_id']!=d['map_id']:raise RuntimeError('旧目标不能用于当前地图')
 write(folder()/'accuracy_target.json',t);save(selected=name)
def preview(name):
 choose(name);save(preview=None);run(['bash','MPPI导航.sh','return-preview'],45)
 r=read(max(folder().glob('protected-preview-*.json'),key=lambda p:p.stat().st_mtime))
 if not r.get('preview_passed'):raise RuntimeError('预演未通过')
 save(preview=dict(name=name,at=time.time(),pose=r['last_pose']))
 print('预演通过。请在RViz确认障碍被识别且路径从外侧绕行，再选择开始导航。')
def navigate(name):
 d=state();check_session(d);health();p=d.get('preview')
 if not p or p['name']!=name or not 0<=time.time()-p['at']<60:raise RuntimeError('请先对该点预演，预演仅60秒内有效')
 # If manually moved after preview, require a fresh preview. Map-frame pose from fresh data.
 import numpy as np
 r=folder();inp=read(r/'input.json');loc=read(r/'localization.json');v=inp['pose']['pose'];T=np.array(loc['transform']);xyz=T[:3,:3]@v[:3]+T[:3,3]
 x,y,z,w=v[3:];norm=x*x+y*y+z*z+w*w
 if not math.isfinite(norm) or abs(norm-1)>.02:raise RuntimeError('姿态四元数无效')
 forward=T[:3,:3]@np.array([1-2*(y*y+z*z)/norm,2*(x*y+w*z)/norm,2*(x*z-w*y)/norm]);yaw=math.atan2(forward[1],forward[0]);turn=math.atan2(math.sin(yaw-p['pose'][2]),math.cos(yaw-p['pose'][2]))
 if math.hypot(xyz[0]-p['pose'][0],xyz[1]-p['pose'][1])>.05 or abs(turn)>.1:raise RuntimeError('预演后位置/朝向变化，请重新预演')
 choose(name);save(preview=None)
 run(['bash','MPPI导航.sh','return-execute'],115)
 print('任务结束，请确认实机停稳并测量。软件结果不能代替实测。')
def status():
 d=state();print(json.dumps(d,ensure_ascii=False,indent=2));run(['/usr/bin/python3','desktop/control.py','status']);run(['bash','MPPI导航.sh','status'])
def view(mode):
 if mode=='mapping':run(['bash','desktop/open_view.sh']);return
 # Avoid duplicate RViz windows created by this console.
 saved=state().get('rviz_pid')
 if saved:
  try:
   cmd=Path('/proc')/str(saved)/'cmdline'
   if b'rviz2' in cmd.read_bytes():print('导航RViz已打开');return
  except OSError:pass
 log=ROOT/'demo/rviz.log';f=log.open('a');p=subprocess.Popen(['bash','MPPI导航.sh','rviz'],cwd=ROOT,stdout=f,stderr=f,start_new_session=True);f.close();save(rviz_pid=p.pid)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='menu',choices=['menu','status','start','finish','record','preview','navigate','stop','rviz']);parser.add_argument('name',nargs='?');args=parser.parse_args()
 if args.action=='stop':stop_motion();print('已请求取消导航；请确认实机停稳');return
 lock=(ROOT/'demo/console.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def dispatch(action,name=None):
  if action=='start':start_mapping()
  elif action=='finish':finish_mapping()
  elif action=='record':record(name or input('目标点名称：').strip())
  elif action in ('preview','navigate'):
   print('已保存点：'+'、'.join(state().get('points',{})));n=name or input('选择点名称：').strip()
   (preview if action=='preview' else navigate)(n)
  elif action=='stop':stop_motion()
  elif action=='rviz':view('mapping' if state()['phase']=='mapping' else 'navigation')
  else:status()
 if args.action!='menu':dispatch(args.action,args.name);return
 while True:
  print('\n=== Go2W 演示控制台 ===  阶段：'+state()['phase'])
  print('1 开始新扫图（先静止）\n2 结束扫图并保存（先停稳）\n3 保存当前位置为目标点\n4 选择点并预览路径（不运动）\n5 开始导航（会运动，Ctrl+C取消）\n6 停止导航\n7 打开当前阶段RViz\n8 查看状态及已保存点\n0 退出菜单（定位继续运行）')
  try:choice=input('请选择：').strip()
  except (EOFError,KeyboardInterrupt):break
  if choice=='0':break
  action={'1':'start','2':'finish','3':'record','4':'preview','5':'navigate','6':'stop','7':'rviz','8':'status'}.get(choice)
  if not action:print('请输入0–8');continue
  try:dispatch(action)
  except Exception as e:print('未完成：'+str(e))
if __name__=='__main__':
 try:main()
 except (Exception,KeyboardInterrupt) as e:print('未完成：'+str(e),file=sys.stderr);sys.exit(1)
