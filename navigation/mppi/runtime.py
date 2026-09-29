"""Own all Nav2 processes; no child links any Unitree SDK or motion interface."""
import subprocess,os,time,json,signal
from pathlib import Path
root=Path('/state');root.mkdir(exist_ok=True);children=[];stop=False;error=None
mode=os.environ.get('MPPI_MODE','live')
def sig(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,sig);signal.signal(signal.SIGINT,sig)
def start(role,args):
 f=(root/(role+'.log')).open('w');p=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);children.append((role,p,f))
def state(phase):
 d=dict(phase=phase,error=error,mode=mode,actuation_enabled=False,updated=time.time(),children=[dict(role=r,pid=p.pid,alive=p.poll() is None) for r,p,_ in children]);t=root/'runtime.tmp';t.write_text(json.dumps(d));t.replace(root/'runtime.json')
try:
 start('inputs',['python3','/work/inputs.py']);state('waiting_inputs');deadline=time.monotonic()+20
 while not stop:
  if children[0][1].poll() is not None:raise RuntimeError('Input adapter exited')
  try:
   d=json.loads((root/'input.json').read_text())
   if d['ready'] and time.time()-d['updated']<1:break
  except (OSError,ValueError):pass
  if time.monotonic()>deadline:raise RuntimeError('No fresh inputs within 20s')
  time.sleep(.1)
 if stop:raise RuntimeError('Stopped during initialization')
 selected=Path('/work/selection.json').exists() and mode=='live'
 if selected:
  start('localization',['python3','/work/localization.py']);deadline=time.monotonic()+20
  while not stop:
   if children[-1][1].poll() is not None:raise RuntimeError('Saved-map localizer exited')
   try:
    loc=json.loads((root/'localization.json').read_text())
    if loc.get('ready'):break
   except (OSError,ValueError):pass
   if time.monotonic()>deadline:raise RuntimeError('Saved-map localization did not validate')
   time.sleep(.1)
 start('heading_view',['python3','/work/heading_view.py'])
 common=['--ros-args' ,'--params-file','/work/params.yaml']
 if selected:start('map_server',['/opt/ros/humble/lib/nav2_map_server/map_server']+common)
 for pkg,exe,remap in [('nav2_planner','planner_server',[]),('nav2_controller','controller_server',['-r','cmd_vel:=/mppi/cmd_vel_raw']),('nav2_velocity_smoother','velocity_smoother',['-r','cmd_vel:=/mppi/cmd_vel_raw','-r','cmd_vel_smoothed:=/mppi/cmd_vel_smoothed']),('nav2_bt_navigator','bt_navigator',[]),('nav2_lifecycle_manager','lifecycle_manager',['-r','__node:=lifecycle_manager'])]:
  start(exe,['/opt/ros/humble/lib/'+pkg+'/'+exe]+common+remap)
 start('lifecycle_watch',['python3','/work/lifecycle_watch.py'])
 bad_since=None
 while not stop:
  dead=[r for r,p,_ in children if p.poll() is not None]
  if dead:raise RuntimeError('Child exited: '+','.join(dead))
  d=json.loads((root/'input.json').read_text());good=d['ready'] and time.time()-d['updated']<1
  if not good:
   if bad_since is None:bad_since=time.monotonic()
   if time.monotonic()-bad_since>.5:raise RuntimeError('Navigation inputs stale: '+json.dumps(d))
  else:bad_since=None
  if selected:
   loc=json.loads((root/'localization.json').read_text())
   if not loc.get('ready') or time.time()-loc['updated']>1:raise RuntimeError('Saved-map localization lost: '+str(loc))
  state('running');time.sleep(.1)
except Exception as e:error=str(e)
finally:
 state('stopping')
 for _,p,_ in reversed(children):
  if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
 deadline=time.monotonic()+5
 for _,p,f in reversed(children):
  try:p.wait(timeout=max(.01,deadline-time.monotonic()))
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  f.close()
 state('stopped')
if error:raise SystemExit(error)
