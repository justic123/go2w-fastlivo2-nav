#!/usr/bin/env python3
"""Serialized background exports, independent of capture/control locks."""
import fcntl,os,subprocess,sys,time,signal
from service_core import ROOT,atomic,read,birth,alive,owned_alive,signal_owned
run=sys.argv[1];folder=ROOT/run
if folder.parent!=ROOT or not folder.is_dir():raise SystemExit('Invalid run')
status=folder/'export_status.json';info=dict(run=run,pid=os.getpid(),birth=birth(os.getpid()),phase='queued')
stop_signal=None
child=None
p=None
def request_stop(signum,_frame):
 global stop_signal
 stop_signal=signum
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,request_stop)
def check_stop():
 if stop_signal:raise InterruptedError('Export interrupted by signal '+str(stop_signal))
def cleanup_child():
 # A stopped child cannot handle TERM until continued. Only signal our recorded group.
 if child and owned_alive(child):
  signal_owned(child,signal.SIGCONT,True)
  signal_owned(child,signal.SIGTERM,True)
  deadline=time.monotonic()+3
  while owned_alive(child) and time.monotonic()<deadline:time.sleep(.05)
  if owned_alive(child):signal_owned(child,signal.SIGKILL,True)
 if p:
  try:p.wait(timeout=2)
  except subprocess.TimeoutExpired:pass
atomic(status,info)
try:
 with (ROOT/'export_queue.lock').open('a') as lock:
  while True:
   check_stop()
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:time.sleep(.2)
  os.nice(10)
  if not (folder/'sensors.bag').exists() or (folder/'sensors.bag.active').exists():raise RuntimeError('Bag not sealed')
  voxel=read(folder/'capture_settings.json').get('rgb_voxel',.02)
  jobs=[('imu_check_exit',[str(ROOT/'check_imu_continuity.py'),str(folder/'bridge/imu_timing.csv'),str(folder/'imu_quality.json')]),('map_export_exit',[str(ROOT/'mapping/export_map.py'),str(folder)]),('rgb_map_export_exit',[str(ROOT/'mapping/export_rgb_map.py'),str(folder),'--voxel',str(voxel)])]
  result={}
  env=dict(HOME='/home/unitree',USER='unitree',LANG='C.UTF-8',PATH='/usr/bin:/bin',OPENBLAS_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
  for name,args in jobs:
   check_stop();info.update(phase='running',stage=name,updated=time.time());atomic(status,info)
   with (folder/(name+'.log')).open('w') as log:
    p=subprocess.Popen(['bash','-c','source /opt/ros/noetic/setup.bash; exec python3 "$@"','_']+args,env=env,stdout=log,stderr=log,close_fds=True,start_new_session=True)
    child=dict(pid=p.pid,birth=birth(p.pid));info['child']=child
    paused=False
    try:
     while p.poll() is None:
      check_stop()
      capture=read(ROOT/'continuous_capture.json')
      board_mapping=alive(capture) and read(ROOT/'compute_location.json').get('mode','board')=='board'
      if board_mapping!=paused:
       signal_owned(child,signal.SIGSTOP if board_mapping else signal.SIGCONT,True)
       paused=board_mapping;info.update(phase='paused_for_mapping' if paused else 'running',stage=name,updated=time.time());atomic(status,info)
      time.sleep(.2)
     check_stop();result[name]=p.returncode
    finally:
     cleanup_child();child=None;p=None
  result['bag_sealed']=True;atomic(folder/'completion.json',result)
  info.update(phase='complete' if not any(result[k] for k in ['imu_check_exit','map_export_exit','rgb_map_export_exit']) else 'failed',results=result,updated=time.time());atomic(status,info)
except Exception as exc:
 cleanup_child();info.update(phase='failed',error=str(exc),updated=time.time());atomic(status,info)
 raise SystemExit(128+stop_signal if stop_signal else 1)
