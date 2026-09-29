"""Bounded service control. Locks cover mutations only; children never inherit them."""
import fcntl,json,os,re,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(os.environ.get('GO2W_SERVICE_ROOT','/home/unitree/fast_livo2_port/build1'))
FILES={'capture':'continuous_capture.json','nav':'nav2_preview_state.json'}
def atomic(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()));tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.replace(str(tmp),str(path))
def read(path,default=None):
 try:return json.loads(Path(path).read_text())
 except (FileNotFoundError,json.JSONDecodeError):return {} if default is None else default
def birth(pid):
 try:
  fields=Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()
  return None if fields[0]=='Z' else fields[19]
 except (FileNotFoundError,ProcessLookupError):return None
def alive(item):return bool(item and birth(item.get('pid',0))==item.get('birth') and item.get('birth') is not None)
def group_members(item):
 # Session leaders are created with start_new_session; a reused leader PID never matches.
 pid=item.get('pid',0);b=birth(pid)
 if b is not None and b!=item.get('birth'):return []
 result=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   fields=(d/'stat').read_text().rsplit(')',1)[1].split()
   if fields[0]!='Z' and int(fields[2])==pid and int(fields[3])==pid:result.append(int(d.name))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return result
def owned_alive(item):return alive(item) or bool(group_members(item))
def children(item):
 return [x for x in read(ROOT/item['run']/'runtime.json').get('children',[]) if owned_alive(x)] if item and item.get('run') else []
def snapshot(service):
 s=read(ROOT/FILES[service]);running=alive(s)
 rt=read(ROOT/s['run']/'runtime.json') if s.get('run') else {}
 remaining=children(s)
 phase=rt.get('phase','legacy' if running else 'stopped')
 if not running and remaining:phase='orphaned'
 elif not running and phase not in ('stopped','failed'):phase='stopped'
 if running and phase=='running' and service=='capture' and (ROOT/s['run']/'capture_settings.json').exists() and read(ROOT/s['run']/'capture_settings.json').get('compute_location','board')=='board':
  try:
   with (ROOT/s['run']/'bridge/odometry.jsonl').open('rb') as f:
    f.seek(0,2);f.seek(max(0,f.tell()-1024));last=json.loads(f.read().splitlines()[-1])
   s['data_age_s']=time.time()-last['receipt']
   if not 0<=s['data_age_s']<2:phase='degraded'
  except (OSError,ValueError,IndexError,KeyError):phase='degraded'
 if running and phase=='running' and service=='nav' and (ROOT/s['run']/'nav_config.yaml').exists():
  h=read('/dev/shm/go2w_nav/adapter_status.json');s['input_health']=h
  if not 0<=time.time()-h.get('last_check',0)<1 or h.get('pose_age_s') is None or h.get('cloud_age_s') is None or not 0<=h['pose_age_s']<.85 or not 0<=h['cloud_age_s']<.8:phase='degraded'
 s.update(running=running,ready=running and phase=='running',phase=phase,children_alive=len(remaining),error=rt.get('error'),lifecycle_version=s.get('lifecycle_version',1))
 if s.get('run'):s['export']=read(ROOT/s['run']/'export_status.json',{'phase':'not_queued'})
 return s
class ControlLock:
 def __init__(self,path,seconds=2):self.path=path;self.seconds=seconds
 def __enter__(self):
  self.f=self.path.open('a');end=time.monotonic()+self.seconds
  while True:
   try:fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB);return self
   except BlockingIOError:
    if time.monotonic()>end:self.f.close();raise RuntimeError('Another control request is busy; retry status shortly')
    time.sleep(.05)
 def __exit__(self,*_):self.f.close()
def signal_owned(s,sig,group=False):
 try:
  if group and group_members(s):os.killpg(s['pid'],sig)
  elif alive(s):os.kill(s['pid'],sig)
 except ProcessLookupError:pass
def control(service,action,run=None,wait_seconds=35):
 if action=='status':return snapshot(service)
 if action not in ('start','stop','restart'):raise ValueError('start/stop/restart/status only')
 if action=='restart':
  stopped=control(service,'stop',wait_seconds=wait_seconds)
  if stopped['running'] or stopped['children_alive']:raise RuntimeError('Stop unfinished; refuse restart')
  return control(service,'start',run,wait_seconds)
 lock=ROOT/(service+'_control_v2.lock')
 with ControlLock(lock):
  s=snapshot(service)
  if action=='start':
   if s['running']:
    if s['phase'] in ('stopping','closing_bag','flush_pending'):raise RuntimeError('Service is stopping; inspect status before start')
    if s['ready']:return s
    # An already-starting service is reused; wait outside the lock below.
   else:
    if s['children_alive']:raise RuntimeError('Owned child processes remain; run stop to recover before start')
    if service=='nav' and read(ROOT/'compute_location.json').get('mode','board')=='desktop' and not read(ROOT/'desktop_navigation.json').get('session'):raise RuntimeError('Start desktop navigation with a bound mapping session first')
    if service=='nav' and not snapshot('capture').get('ready'):raise RuntimeError('Mapping not ready; inspect capture status first')
    if not run or not re.fullmatch('[a-zA-Z0-9_-]+',run):raise ValueError('Invalid run name')
    folder=ROOT/run;folder.mkdir(exist_ok=False)
    atomic(folder/'runtime.json',dict(phase='starting',children=[],error=None))
    runner=os.environ.get('GO2W_SERVICE_RUNNER',str(ROOT/'lifecycle/pipeline_runner.py'))
    with (ROOT/(run+'.log')).open('w') as log:
     p=subprocess.Popen([sys.executable,runner,service,run],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
    s=dict(pid=p.pid,birth=birth(p.pid),run=run,lifecycle_version=2)
    atomic(ROOT/FILES[service],s)
  else:
   if s['running']:
    if s['lifecycle_version']!=2:raise RuntimeError('Legacy pipeline must be migrated once; no broad kill or blind restart')
    signal_owned(s,signal.SIGTERM)
   elif s['children_alive']:
    # Recover only exact PID+birth groups from this run's registry.
    for item in children(s):signal_owned(item,signal.SIGINT if item.get('role')=='bag' else signal.SIGTERM,True)
   else:return s
 # Never hold the command lock while waiting. Concurrent status/start/stop stay responsive.
 end=time.monotonic()+wait_seconds;recovery_deadline=time.monotonic()+5
 while time.monotonic()<end:
  current=snapshot(service)
  if action=='stop' and not current['running'] and current['children_alive'] and time.monotonic()>recovery_deadline:
   for item in children(current):
    if item.get('role')!='bag':signal_owned(item,signal.SIGKILL,True)
  if current.get('run')!=s['run']:return current
  if action=='start':
   if current['ready'] or not current['running']:return current
  elif not current['running'] and not current['children_alive']:return current
  time.sleep(.1)
 current=snapshot(service);current['wait_timed_out']=True;return current
def main(service):
 try:
  result=control(service,sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
  print(json.dumps(result,ensure_ascii=False),flush=True)
  action=sys.argv[1]
  bad=result.get('wait_timed_out') or (action in ('start','restart') and not result.get('ready')) or (action=='stop' and (result.get('running') or result.get('children_alive')))
  raise SystemExit(1 if bad else 0)
 except (RuntimeError,ValueError,OSError) as e:print(json.dumps(dict(error=str(e),service=service)),flush=True);raise SystemExit(1)
