"""Container supervisor: ROS1 mapping only, no navigation or SDK actuation."""
import os,sys,subprocess,time,signal,json
from backlog_policy import BacklogGuard
lag_guard=BacklogGuard(soft=2.,hard=5.,grace=5.)
from pathlib import Path
root=Path('/work');run=os.environ['GO2W_DESKTOP_RUN'];folder=root/'runs'/run;folder.mkdir(parents=True,exist_ok=True);stop=False;children=[];logs=[]
def onstop(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,onstop);signal.signal(signal.SIGINT,onstop)
env=dict(os.environ,ROS_MASTER_URI='http://127.0.0.1:11331',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',OMP_THREAD_LIMIT='4',OMP_WAIT_POLICY='PASSIVE',OPENBLAS_NUM_THREADS='1',GO2W_IMAGE_PROFILE='10hz',GO2W_SOURCE_PORT='11335')
def start(role,args):
 f=(folder/(role+'.log')).open('w');logs.append(f);p=subprocess.Popen(args,env=env,stdout=f,stderr=f,start_new_session=True);children.append((role,p));return p
def state(phase,error=None):
 p=folder/'runtime.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(dict(phase=phase,error=error,children=[dict(role=k,pid=p.pid,running=p.poll() is None) for k,p in children])));t.replace(p)
error=None
try:
 state('starting');start('master',['roscore','-p','11331'])
 for _ in range(40):
  if stop:raise RuntimeError('Stop requested')
  try:
   if subprocess.run(['rosparam','list'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1).returncode==0:break
  except subprocess.TimeoutExpired:pass
  time.sleep(.2)
 else:raise RuntimeError('Local ROS master unavailable')
 subprocess.run(['rosparam','set','/use_sim_time','true'],env=env,check=True)
 for name,ns in [('livo.yaml','/go2w_lio'),('camera.yaml','/go2w_lio/laserMapping')]:subprocess.run(['rosparam','load',str(root/name),ns],env=env,check=True,timeout=5)
 start('bag',['/opt/ros/noetic/lib/rosbag/record','--lz4','--buffsize','256','-O',str(folder/'sensors.bag'),'/go2w_lio/points','/go2w_lio/imu','/go2w_livo/jpeg','/go2w_lio/odometry','/go2w_lio/cloud','/go2w_lio/processing_lag'])
 start('decode',['python3',str(root/'decode_jpeg.py'),str(folder/'images.json'),'0'])
 start('algorithm',[str(root/'ws/devel/lib/fast_livo/fastlivo_mapping'),'__ns:=/go2w_lio','/aft_mapped_to_init:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud','/path:=/go2w_lio/path'])
 start('view',['python3',str(root/'ros1_view_source.py')])
 start('monitor',['python3',str(root/'monitor.py'),str(folder/'health.json')])
 start('receive',['python3',str(root/'raw_receiver.py'),str(folder/'transport.json')])
 state('running')
 while not stop:
  dead=[k for k,p in children if p.poll() is not None]
  if dead:raise RuntimeError('Child exited: '+','.join(dead))
  health=folder/'health.json'
  if health.exists():
   h=json.loads(health.read_text())
   if h.get('lag_samples',0)>=20:lag_guard.check(h.get('lag_last_s',0),time.monotonic())
  time.sleep(.2)
except Exception as e:error=str(e);print(error,flush=True)
finally:
 state('stopping',error)
 # Recorder receives SIGINT and is allowed to finish its index before master exits.
 for k,p in reversed(children):
  if k=='master':continue
  if p.poll() is None:
   os.killpg(p.pid,signal.SIGINT if k=='bag' else signal.SIGTERM)
   try:p.wait(timeout=15 if k=='bag' else 3)
   except subprocess.TimeoutExpired:
    if k=='bag':state('closing_bag',error);p.wait()
    else:os.killpg(p.pid,signal.SIGKILL);p.wait()
 for k,p in children:
  if k=='master' and p.poll() is None:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 state('failed' if error else 'stopped',error)
