#!/usr/bin/env python3
"""Isolated offline comparison. No driver, actuator, capture state or power change."""
import os,sys,time,json,signal,subprocess,shutil
from pathlib import Path
R=Path('/home/unitree/fast_livo2_port/build1');out=R/'board-threads-benchmark';out.mkdir(exist_ok=True)
def birth(pid):
 try:return Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()[19]
 except OSError:return None
state=json.loads((R/'livo-manual-20260928-145205-18571/export_status.json').read_text());pid=state['pid']
if birth(pid)==state['birth'] and os.getpgid(pid)==pid:
 os.killpg(pid,signal.SIGSTOP);(out/'paused_export.json').write_text(json.dumps(state,indent=2))
else:raise RuntimeError('Export identity changed; inspect before retry')
env=dict(HOME='/home/unitree',USER='unitree',LANG='C.UTF-8',PATH='/usr/bin:/bin',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',GO2W_IMAGE_PROFILE='5hz')
raw=subprocess.check_output(['/bin/bash','-c','source /opt/ros/noetic/setup.bash; source '+str(R)+'/ws/devel/setup.bash; env -0'],env=env)
env.update(dict(x.decode().split('=',1) for x in raw.split(b'\0') if b'=' in x));env.update(ROS_MASTER_URI='http://127.0.0.1:11341',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost')
for threads in (2,4):
 d=out/('threads%d'%threads);d.mkdir(exist_ok=True);children=[];env['OMP_THREAD_LIMIT']=str(threads);env['ROS_LOG_DIR']=str(d/'ros_logs')
 def start(name,args):
  f=(d/(name+'.log')).open('w');p=subprocess.Popen(args,env=env,stdout=f,stderr=f,start_new_session=True);children.append((p,birth(p.pid)));return p
 def cmd(args):return subprocess.run(args,env=env,check=True,timeout=8,stdout=subprocess.DEVNULL)
 try:
  start('master',['/opt/ros/noetic/bin/roscore','-p','11341']);time.sleep(3)
  cmd(['/opt/ros/noetic/bin/rosparam','set','/use_sim_time','true'])
  for path,ns in [('mapping/livo_display_candidate.yaml','/go2w_lio'),('camera/livo_diagnostic/camera_candidate.yaml','/go2w_lio/laserMapping')]:cmd(['/opt/ros/noetic/bin/rosparam','load',str(R/path),ns])
  node=start('node',[str(R/'ws/devel/lib/fast_livo/fastlivo_mapping'),'__ns:=/go2w_lio','/aft_mapped_to_init:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud'])
  start('decode',['/usr/bin/python3',str(R/'mapping/decode_jpeg.py'),str(d/'image_summary.json'),'0']);time.sleep(3)
  wall=time.monotonic();player=start('player',['/opt/ros/noetic/lib/rosbag/play','--clock','--duration=60','--delay=2',str(R/'desktop-comparison-240s.bag')]);samples=[]
  while time.monotonic()-wall<105:
   log=R/'ws/src/FAST-LIVO2/Log/mat_out.txt';lines=log.read_text().splitlines() if log.exists() else []
   progress=float(lines[-1].split()[0]) if lines else 0
   stat=Path('/proc/%d/status'%node.pid).read_text();rss=[s for s in stat.splitlines() if s.startswith('VmRSS:')][0]
   samples.append(dict(wall_s=time.monotonic()-wall,state_relative_s=progress,rss=rss))
   if node.poll() is not None:raise RuntimeError('Algorithm exited')
   if player.poll() is not None and progress>59:break
   time.sleep(1)
  (d/'samples.json').write_text(json.dumps(samples,indent=2));shutil.copy2(log,d/'mat_out.txt')
  print(json.dumps(dict(threads=threads,last=samples[-1],at60=min(samples,key=lambda s:abs(s['wall_s']-62)))) ,flush=True)
 finally:
  for p,b in reversed(children):
   if birth(p.pid)==b:os.killpg(p.pid,signal.SIGTERM)
  time.sleep(2)
  for p,b in reversed(children):
   if birth(p.pid)==b:
    try:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   try:p.wait(timeout=2)
   except subprocess.TimeoutExpired:pass
