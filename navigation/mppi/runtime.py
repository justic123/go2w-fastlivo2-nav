"""Own all Nav2 processes; no child links any Unitree SDK or motion interface."""
import subprocess,os,time,json,signal
from pathlib import Path
from status_store import publish as publish_status
from startup_gate import StartupGate
from runtime_health import RuntimeHealth
root=Path('/state');root.mkdir(exist_ok=True);children=[];stop=False;error=None
mode=os.environ.get('MPPI_MODE','live')
def sig(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,sig);signal.signal(signal.SIGINT,sig)
def start(role,args):
 f=(root/(role+'.log')).open('w');p=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);children.append((role,p,f))
def state(phase):
 d=dict(phase=phase,error=error,mode=mode,actuation_enabled=False,updated=time.time(),children=[dict(role=r,pid=p.pid,alive=p.poll() is None) for r,p,_ in children]);publish_status(root,'runtime',d)
try:
 start('inputs',['python3','/work/inputs.py']);state('waiting_inputs');deadline=time.monotonic()+20
 while not stop:
  if children[0][1].poll() is not None:raise RuntimeError('Input adapter exited')
  try:
   d=json.loads((root/'input.json').read_text())
   if d['ready'] and 0<=time.time()-d['updated']<1:break
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
 common=['--ros-args' ,'--params-file',os.environ.get('GO2W_MPPI_CONFIG','/work/params.yaml')]
 if selected:start('map_server',['/opt/ros/humble/lib/nav2_map_server/map_server']+common)
 for pkg,exe,remap in [('nav2_planner','planner_server',[]),('nav2_controller','controller_server',['-r','cmd_vel:=/mppi/cmd_vel_raw']),('nav2_velocity_smoother','velocity_smoother',['-r','cmd_vel:=/mppi/cmd_vel_raw','-r','cmd_vel_smoothed:=/mppi/cmd_vel_smoothed']),('nav2_bt_navigator','bt_navigator',[]),('nav2_lifecycle_manager','lifecycle_manager',['-r','__node:=lifecycle_manager'])]:
  start(exe,['/opt/ros/humble/lib/'+pkg+'/'+exe]+common+remap)
 start('lifecycle_watch',['python3','/work/lifecycle_watch.py'])
 startup=StartupGate(time.monotonic());settled=False;availability=RuntimeHealth()
 while not stop:
  dead=[r for r,p,_ in children if p.poll() is not None]
  if dead:raise RuntimeError('Child exited: '+','.join(dead))
  d=json.loads((root/'input.json').read_text());good=d['ready'] and 0<=time.time()-d['updated']<1
  if d.get('fault'):raise RuntimeError('Navigation input fault: '+str(d['fault']))
  if not settled:
   try:life=json.loads((root/'lifecycle.json').read_text())
   except (OSError,ValueError):life={}
   settled=startup.observe(time.monotonic(),good,bool(life.get('ready') and 0<=time.time()-life.get('updated',0)<1))
   if not settled:
    state('warming_up');time.sleep(.1);continue
  problem=None if good else 'Navigation inputs stale: '+json.dumps(d)
  life=json.loads((root/'lifecycle.json').read_text())
  if not life.get('ready') or not 0<=time.time()-life.get('updated',0)<1:
   problem='Nav2 lifecycle unverified: '+str(life.get('states'))
  if selected:
   loc=json.loads((root/'localization.json').read_text())
   if loc.get('fault'):raise RuntimeError('Saved-map localization fault: '+str(loc))
   if not loc.get('ready') or not 0<=time.time()-loc['updated']<1:
    problem='Saved-map localization unverified: '+str(loc.get('issue') or loc.get('stats'))
  # Existing action guards reject any phase other than running, stop and cancel
  # the goal. Keeping these observers alive never resumes an interrupted action.
  phase,error=availability.observe(time.monotonic(),problem)
  state(phase);time.sleep(.1)
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
