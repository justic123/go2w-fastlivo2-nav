#!/usr/bin/env python3
"""Own each child process group explicitly. Stop recording before queuing exports."""
import json,os,signal,subprocess,sys,time,shutil,fcntl,socket
from pathlib import Path
from service_core import ROOT,atomic,read,birth,alive,owned_alive,signal_owned
from recording_policy import AuxiliaryRecording
service,run=sys.argv[1:3];folder=ROOT/run;folder.mkdir(exist_ok=True)
stop=False;items=[];handles=[];primary=[];error=None;phase='starting';bag_sealed=False;aux_recording=None;recorder=None
lock=(ROOT/(service+'_pipeline_v2.lock')).open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:atomic(folder/'runtime.json',dict(phase='failed',children=[],error='Pipeline lock already held'));raise SystemExit(1)
def status(new_phase=None):
 global phase
 if new_phase:phase=new_phase
 atomic(folder/'runtime.json',dict(phase=phase,children=items,error=error,updated=time.time(),bag_sealed=bag_sealed,supervisor_pid=os.getpid(),recording=aux_recording.state if aux_recording else None))
def request_stop(*_):
 global stop
 stop=True
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,request_stop)
status()
def environment(distro):
 script='source /opt/ros/'+distro+'/setup.bash; '
 if distro=='noetic':script+='source '+str(ROOT/'ws/devel/setup.bash')+'; '
 script+='env -0'
 env=dict(HOME='/home/unitree',USER='unitree',LANG='C.UTF-8',PATH='/usr/bin:/bin',OPENBLAS_NUM_THREADS='1',OMP_THREAD_LIMIT='2',OMP_WAIT_POLICY='PASSIVE')
 raw=subprocess.check_output(['/bin/bash','-c',script],env=env,timeout=8)
 out=dict(v.decode().split('=',1) for v in raw.split(b'\0') if b'=' in v)
 if distro=='noetic':out.update(ROS_MASTER_URI='http://127.0.0.1:11321',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',ROS_LOG_DIR=str(folder/'ros_logs'))
 else:out.update(ROS_DOMAIN_ID='78',ROS_LOCALHOST_ONLY='1')
 return out
def launch(role,args,env):
 if stop:raise RuntimeError('Stop requested during startup')
 f=(folder/(role+'.log')).open('w');handles.append(f)
 p=subprocess.Popen(args,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True,close_fds=True)
 item=dict(role=role,pid=p.pid,birth=birth(p.pid));items.append(item);primary.append(item);status();return item

def wait_for(test,seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if stop:raise RuntimeError('Stop requested during startup')
  dead=[x['role'] for x in primary if not alive(x)]
  if dead:raise RuntimeError('Pipeline child exited: '+','.join(dead))
  if test():return
  time.sleep(.1)
 raise RuntimeError('Startup readiness timed out')
def stop_child(item,sig,seconds,force=True):
 if not owned_alive(item):return
 signal_owned(item,sig,True);end=time.monotonic()+seconds
 while owned_alive(item) and time.monotonic()<end:time.sleep(.05)
 if owned_alive(item) and force:
  signal_owned(item,signal.SIGKILL,True);end=time.monotonic()+2
  while owned_alive(item) and time.monotonic()<end:time.sleep(.05)

def discover_descendants():
 parents={x['pid'] for x in items if alive(x)};known=set(parents);found=True
 table=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   fields=(d/'stat').read_text().rsplit(')',1)[1].split()
   if fields[0]!='Z':table.append((int(d.name),int(fields[1]),fields[19]))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 while found:
  found=False
  for pid,ppid,b in table:
   if ppid in parents and pid not in known:
    known.add(pid);parents.add(pid);found=True
    # Descendants sharing a primary group are already covered by its group signal.
    try:
     if os.getpgid(pid)==pid:items.append(dict(role='descendant',pid=pid,birth=b))
    except ProcessLookupError:pass
 status()
def fresh_odom():
 try:
  with (folder/'bridge/odometry.jsonl').open('rb') as f:
   f.seek(0,2);size=f.tell();f.seek(max(0,size-1024));lines=f.read().splitlines()
  d=json.loads(lines[-1]);return 0<=time.time()-d['receipt']<2
 except (OSError,ValueError,IndexError,KeyError):return False
sensor_only=read(ROOT/'compute_location.json').get('mode','board')=='desktop'
try:
 for port in ([11321,11329 if sensor_only else 11325] if service=='capture' else [11327]):
  with socket.socket() as sock:
   sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   try:sock.bind(('127.0.0.1',port))
   except OSError:raise RuntimeError('Port %d still in use by another process'%port)
 if service=='capture':
  free_bytes=shutil.disk_usage(ROOT).free
  if free_bytes<5*1024**3:raise RuntimeError('Disk reserve reached before capture startup')
  if sensor_only:aux_recording=AuxiliaryRecording(free_bytes)
  # Unknown or legacy owners are reported, not killed. Never claim a second sensor stack.
  for procdir in Path('/proc').iterdir():
   if not procdir.name.isdigit():continue
   try:
    args=(procdir/'cmdline').read_bytes().split(b'\0');name=Path(args[0].decode()).name
    if name in ('xt16_driver','unitree_slam','fastlivo_mapping'):raise RuntimeError('Conflicting external/legacy PID '+procdir.name+': '+name)
   except (FileNotFoundError,ProcessLookupError,PermissionError):pass
  env=environment('noetic');max_radius=95 if (ROOT/'navigation_profile').exists() and (ROOT/'navigation_profile').read_text().strip()=='floor' else 20
  shutil.copy2(ROOT/'mapping/livo_display_candidate.yaml',folder/'livo_config.yaml');shutil.copy2(ROOT/'camera/livo_diagnostic/camera_candidate.yaml',folder/'camera_config.yaml')
  image_profile=read(ROOT/'image_profile.json').get('mode','baseline')
  if image_profile not in ('baseline','5hz','10hz'):raise RuntimeError('Invalid image profile')
  env['GO2W_IMAGE_PROFILE']=image_profile
  atomic(folder/'capture_settings.json',dict(max_radius=max_radius,seconds=0,rgb_voxel=.05 if max_radius==95 else .02,image_profile=image_profile,compute_location='desktop' if sensor_only else 'board'))
  launch('master',['/opt/ros/noetic/bin/roscore','-p','11321'],env)
  def master_ready():
   try:return subprocess.run(['/opt/ros/noetic/bin/rosparam','list'],env=env,timeout=1,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
   except subprocess.TimeoutExpired:return False
  wait_for(master_ready,12)
  for cfg,ns in [(ROOT/'mapping/livo_display_candidate.yaml','/go2w_lio'),(ROOT/'camera/livo_diagnostic/camera_candidate.yaml','/go2w_lio/laserMapping')]:subprocess.run(['/opt/ros/noetic/bin/rosparam','load',str(cfg),ns],env=env,timeout=5,check=True)
  if not aux_recording or aux_recording.state['phase']=='running':
   recorder=launch('bag',['/opt/ros/noetic/lib/rosbag/record','--lz4','--buffsize','256','-O',str(folder/'sensors.bag'),'/go2w_lio/points','/go2w_lio/imu','/go2w_lio/cloud','/go2w_lio/odometry','/go2w_livo/jpeg'],env)
   if aux_recording:primary.remove(recorder)
  if sensor_only:launch('view',['python3',str(ROOT/'lifecycle/raw_source.py'),str(folder/'transport_status.json')],env)
  else:launch('view',['python3',str(ROOT/'mapping/ros1_view_source.py')],env)
  if not sensor_only:launch('node',[str(ROOT/'ws/devel/lib/fast_livo/fastlivo_mapping'),'__ns:=/go2w_lio','/aft_mapped_to_init:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud','/path:=/go2w_lio/path','/mavros/vision_pose/pose:=/go2w_lio/unused_pose'],env)
  launch('driver',['bash','/home/unitree/go2w_slam_setup/helpers/run_driver.sh'],env)
  if not sensor_only:launch('decode',['python3',str(ROOT/'mapping/decode_jpeg.py'),str(folder/'image_summary.json'),'0'],env)
  launch('jpeg',[str(ROOT/'mapping/jpeg_build/livo_jpeg'),'_duration_sec:=0','_rate_hz:='+('10' if image_profile=='10hz' else '5')],env)
  launch('bridge',['python3',str(ROOT/'mapping/mapping_bridge.py'),'--imu-source','ros2','--diagnostic','--point-time-unit','ns','--header-reference','end','--seconds','0','--max-radius',str(max_radius),'--output',str(folder/'bridge')],env)
  if sensor_only:
   # A recorder/driver-ready acquisition service may wait for the desktop connection.
   wait_for(lambda:all(alive(x) for x in primary),5)
  else:
   wait_for(fresh_odom,25)
   # Starting a fresh inertial map requires a stationary initialization period.
   # Do not report ready on the very first odometry sample.
   baseline=json.loads((folder/'bridge/odometry.jsonl').read_text().splitlines()[-1])['position']
   stable_until=time.monotonic()+4
   while time.monotonic()<stable_until:
    if stop:raise RuntimeError('Stop requested during startup')
    if any(not alive(x) for x in primary):raise RuntimeError('Pipeline child exited during initialization')
    if not fresh_odom():raise RuntimeError('Odometry stale during initialization')
    position=json.loads((folder/'bridge/odometry.jsonl').read_text().splitlines()[-1])['position']
    if sum((a-b)**2 for a,b in zip(position,baseline))>.15**2:raise RuntimeError('Initialization moved/drifted >15cm; keep robot stationary and explicitly start a new map')
    time.sleep(.2)
 else:
  env1=environment('noetic');env2=environment('foxy');nav=ROOT/'navigation/nav2'
  source_config=nav/('floor.yaml' if (ROOT/'navigation_profile').exists() and (ROOT/'navigation_profile').read_text().strip()=='floor' else 'preview.yaml')
  sys.path.insert(0,str(nav))
  from fixed_map import configure
  config=folder/'nav_config.yaml';fixed=configure(ROOT,source_config,config)
  if fixed:launch('map_server',['/opt/ros/foxy/lib/nav2_map_server/map_server','--ros-args','--params-file',str(config)],env2)
  if sensor_only:launch('desktop_pose',['python3',str(ROOT/'lifecycle/desktop_nav_receive.py')],env1)
  launch('input_ros1',['python3',str(nav/'input_ros1.py')],env1);launch('input_ros2',['python3',str(nav/'input_ros2.py')],env2)
  launch('planner',['/opt/ros/foxy/lib/nav2_planner/planner_server','--ros-args','-r','__node:=planner_server','--params-file',str(config)],env2)
  launch('controller',['/opt/ros/foxy/lib/nav2_controller/controller_server','--ros-args','--params-file',str(config),'-r','cmd_vel:=/go2w_nav/proposed_cmd_vel'],env2)
  launch('lifecycle',['/opt/ros/foxy/lib/nav2_lifecycle_manager/lifecycle_manager','--ros-args','--params-file',str(config)],env2)
  def nav_ready():
   h=read('/dev/shm/go2w_nav/adapter_status.json');text=(folder/'lifecycle.log').read_text(errors='replace')
   return 'Managed nodes are active' in text and 0<=time.time()-h.get('last_check',0)<1 and h.get('pose_age_s') is not None and 0<=h['pose_age_s']<.85 and h.get('cloud_age_s') is not None and 0<=h['cloud_age_s']<.8
  wait_for(nav_ready,30)
 discover_descendants();status('running');next_scan=time.monotonic()+2
 while not stop:
  dead=[x['role'] for x in primary if not alive(x)]
  if dead:raise RuntimeError('Pipeline child exited: '+','.join(dead))
  if service=='capture':
   free_bytes=shutil.disk_usage(ROOT).free
   if aux_recording:
    aux_recording.tick(free_bytes,time.monotonic(),alive(recorder),lambda:signal_owned(recorder,signal.SIGINT,True))
    bag_sealed=(folder/'sensors.bag').exists() and not (folder/'sensors.bag.active').exists()
   elif free_bytes<5*1024**3:raise RuntimeError('Disk reserve reached')
  if time.monotonic()>=next_scan:discover_descendants();next_scan=time.monotonic()+2
  time.sleep(.2)
except Exception as e:error=str(e);print(error,flush=True)
finally:
 discover_descendants();status('stopping')
 by_role={x['role']:x for x in items}
 if service=='capture':
  # Stop input/SDK first; use the actual recorder executable, never its Python wrapper.
  for role in ['bridge','jpeg','decode','driver']:
   if role in by_role:stop_child(by_role[role],signal.SIGTERM,12 if role=='bridge' else 3)
  if 'bag' in by_role:
   status('closing_bag');stop_child(by_role['bag'],signal.SIGINT,12,force=False)
  for role in ['node','view','master']:
   if role in by_role:stop_child(by_role[role],signal.SIGTERM,3)
  if 'bag' in by_role and alive(by_role['bag']):
   # Never kill a recorder mid-index. Status remains available while it finishes.
   status('flush_pending')
   while alive(by_role['bag']):time.sleep(.2)
  for item in items:
   if item['role']=='descendant':stop_child(item,signal.SIGTERM,2)
  bag_sealed=(folder/'sensors.bag').exists() and not (folder/'sensors.bag.active').exists()
  if aux_recording and recorder:
   aux_recording.state.update(phase='closed' if bag_sealed else 'unsealed')
  (folder/'state_logs').mkdir(exist_ok=True)
  for name in ['mat_pre.txt','mat_out.txt']:
   try:shutil.copy2(ROOT/'ws/src/FAST-LIVO2/Log'/name,folder/'state_logs'/name)
   except FileNotFoundError:pass
  if bag_sealed and not sensor_only:
   atomic(folder/'export_status.json',dict(phase='queued',run=run))
   with (folder/'export_worker.log').open('a') as log:
    subprocess.Popen([sys.executable,str(ROOT/'lifecycle/export_worker.py'),run],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
  elif sensor_only:atomic(folder/'export_status.json',dict(phase='not_applicable',note='Sensor-only bag; map is computed on desktop',run=run))
  else:atomic(folder/'export_status.json',dict(phase='failed' if (folder/'sensors.bag.active').exists() else 'not_applicable',error='No sealed bag; any raw files preserved',run=run))
 else:
  # Simultaneous TERM first, then bounded cleanup of exact owned groups.
  for item in reversed(items):signal_owned(item,signal.SIGTERM,True)
  for item in reversed(items):stop_child(item,signal.SIGTERM,2)
 status('failed' if error else 'stopped')
 for f in handles:f.close()
 lock.close()
