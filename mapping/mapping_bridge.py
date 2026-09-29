#!/usr/bin/env python3
"""Bounded diagnostic bridge. No robot command publishers or navigation clients."""
import argparse,csv,json,os,sys,queue,socket,struct,subprocess,tempfile,threading,time,signal
from collections import deque
from pathlib import Path
import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2,PointField,Imu
from nav_msgs.msg import Odometry
from input_core import convert_cloud,TickClock
from cloud_queue import offer_latest,stale_cloud
p=argparse.ArgumentParser();p.add_argument('--diagnostic',action='store_true',required=True);p.add_argument('--point-time-unit',choices=['ns'],required=True);p.add_argument('--header-reference',choices=['start','end'],required=True);p.add_argument('--seconds',type=int,default=30);p.add_argument('--output',required=True);p.add_argument('--imu-source',choices=['ros2','sdk2'],default='ros2');p.add_argument('--max-radius',type=float,default=20.);args=p.parse_args()
if not 20<=args.max_radius<=95:p.error('max-radius must be 20–95m')
assert args.seconds==0 or 5<=args.seconds<=180
if args.seconds==0 and args.imu_source!="ros2":p.error("continuous capture requires ros2 IMU")
out=Path(args.output);out.mkdir(exist_ok=False)
rospy.init_node('go2w_diagnostic_input_bridge')
manual_stop_requested=False
def terminate(signum,frame):
 global manual_stop_requested
 manual_stop_requested=True
signal.signal(signal.SIGTERM,terminate)
lpub=rospy.Publisher('/go2w_lio/points',PointCloud2,queue_size=3)
ipub=rospy.Publisher('/go2w_lio/imu',Imu,queue_size=1000)
stats=dict(diagnostic_only=True,imu_source=args.imu_source,point_time_unit=args.point_time_unit,header_reference=args.header_reference,imu_time='1ms tick; 500-sample median receipt anchor, uncalibrated',cloud_received=0,cloud_published=0,cloud_queue_dropped=0,cloud_stale_dropped=0,cloud_rejected=0,rejection_reasons={},cloud_missing_imu=0,cloud_imu_warmup_skipped=0,cloud_imu_timeout=0,cloud_imu_empty_batch=0,imu_published=0,odometry_count=0,nonfinite_odometry=0,max_position_norm_m=0.,max_receipt_tick_residual_ms=0.,max_cloud_receipt_age_ms=0.)
stop=threading.Event();errors=queue.Queue();clouds=queue.Queue(maxsize=2);imus=deque(maxlen=4000);lock=threading.Lock();clock=TickClock();children=[];handles=[];samples=[]
odomlog=(out/'odometry.jsonl').open('w')
def odom(m):
 v=[m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z];stats['odometry_count']+=1
 q=m.pose.pose.orientation
 if not np.isfinite(v+[q.x,q.y,q.z,q.w]).all():stats['nonfinite_odometry']+=1;errors.put('Nonfinite odometry');return
 radius=float(np.linalg.norm(v))
 stats['max_position_norm_m']=max(stats['max_position_norm_m'],radius)
 odomlog.write(json.dumps(dict(receipt=time.time(),stamp=m.header.stamp.to_sec(),position=v))+'\n');odomlog.flush()
 # Bound this short local diagnostic; finite output alone does not imply valid tracking.
 if radius>args.max_radius:errors.put('Position exceeded configured radius '+str(args.max_radius)+'m')
sub=rospy.Subscriber('/go2w_lio/odometry',Odometry,odom,queue_size=1000)
def launch(cmd,name):
 f=(out/(name+'.stderr')).open('w');handles.append(f)
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=f,start_new_session=True);children.append(proc);return proc
clean=['env','-i','HOME=/home/unitree','USER=unitree','LANG=C.UTF-8','PATH=/usr/bin:/bin']
cloud_timing=(out/'cloud_timing.jsonl').open('w',buffering=1);handles.append(cloud_timing)
timing=None
if args.imu_source!='ros2':
 timing=(out/'imu_timing.csv').open('w');handles.append(timing);timing.write('wall_ns,mono_ns,tick\n')
def imu_reader(proc):
 try:
  for row in csv.DictReader(b.decode() for b in iter(proc.stdout.readline,b'')):
   if stop.is_set():break
   timing.write(row['receive_unix_ns']+','+row['receive_monotonic_ns']+','+row['tick']+'\n')
   vals=[float(row[k]) for k in ['gx','gy','gz','ax','ay','az']]
   if not np.isfinite(vals).all():raise ValueError('Nonfinite IMU')
   receipt=int(row['receive_unix_ns'])*1e-9;ts=clock.observe(int(row['tick']),receipt)
   if ts is None:continue
   residual=(receipt-ts)*1000;stats['max_receipt_tick_residual_ms']=max(stats['max_receipt_tick_residual_ms'],residual)
   if abs(residual)>500:raise ValueError('Tick/host alignment exceeds 500ms guard')
   m=Imu();m.header.stamp=rospy.Time.from_sec(ts);m.header.frame_id='body_imu_candidate';m.orientation_covariance[0]=-1
   m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z=vals[:3];m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z=vals[3:]
   with lock:
    if len(imus)==imus.maxlen:raise ValueError('IMU buffer overflow')
    imus.append((ts,m))
   # IMU must not wait for a successful lidar frame: delayed/rejected clouds
   # otherwise release seconds of old IMU in a burst and abort live navigation.
   # Keep the deque for lidar interval coverage; FAST-LIVO buffers the live IMU.
   ipub.publish(m);stats['imu_published']+=1
  if not stop.is_set():errors.put('IMU source ended unexpectedly')
 except Exception as e:errors.put(str(e))
def imu_coverage(m):
 # Subscribe only for interval coverage. The independent worker owns publication.
 with lock:
  if len(imus)==imus.maxlen:
   errors.put('IMU buffer overflow');return
  imus.append((m.header.stamp.to_sec(),m))
 stats['imu_published']+=1
def recv_exact(conn,n):
 data=bytearray()
 while len(data)<n:
  chunk=conn.recv(n-len(data))
  if not chunk:raise EOFError('Cloud source ended')
  data.extend(chunk)
 return bytes(data)
def cloud_reader(server):
 try:
  conn,_=server.accept();conn.settimeout(3)
  with conn:
   while not stop.is_set():
    n=struct.unpack('!I',recv_exact(conn,4))[0]
    if n>8192:raise ValueError('IPC metadata too large')
    meta=json.loads(recv_exact(conn,n));size=meta['size']
    if not 0<size<=8_000_000:raise ValueError('IPC cloud size invalid')
    data=recv_exact(conn,size)
    meta['bridge_received']=time.time()
    if stop.is_set():break
    stats['cloud_received']+=1
    stats['cloud_queue_dropped']+=offer_latest(clouds,(meta,data,time.monotonic()))
 except Exception as e:
  if not stop.is_set():errors.put(str(e))
fields=[PointField(n,o,t,1) for n,o,t in [('x',0,7),('y',4,7),('z',8,7),('intensity',12,7),('ring',16,4),('timestamp',18,8)]]
failure=None
try:
 ready_by=time.monotonic()+15
 while not (lpub.get_num_connections() and ipub.get_num_connections()):
  if time.monotonic()>ready_by:raise RuntimeError('Algorithm input subscribers not ready')
  time.sleep(.05)
 with tempfile.TemporaryDirectory(prefix='go2w-bridge-') as tmp:
  address=str(Path(tmp)/'cloud.sock');server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);server.listen(1);server.settimeout(10)
  shell='source /opt/ros/foxy/setup.bash; source /home/unitree/cyclonedds_ws/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml; exec python3 "$1" "$2"'
  threads=[];iproc=None
  if args.imu_source=='ros2':
   imu_sub=rospy.Subscriber('/go2w_lio/imu',Imu,imu_coverage,queue_size=2000,tcp_nodelay=True)
   iproc=launch([sys.executable,str(Path(__file__).with_name('imu_forward_native_runner.py')),str(out)],'imu-forward')
  else:
   iproc=launch(clean+['stdbuf','-oL','/home/unitree/fast_livo2_port/audit/build/lowstate_audit','120'],'imu-source')
   threads=[threading.Thread(target=imu_reader,args=(iproc,),daemon=True)]
   threads[0].start()
  warmup_deadline=time.monotonic()+15
  while not imus:
   if iproc.poll() is not None:raise RuntimeError('IMU worker ended unexpectedly')
   if not errors.empty():raise RuntimeError(errors.get())
   if time.monotonic()>warmup_deadline:raise RuntimeError('IMU discovery/warmup timeout')
   time.sleep(.01)
  launch(clean+['bash','--noprofile','--norc','-c',shell,'bridge',str(Path(__file__).with_name('cloud_source_ros2.py')),address],'cloud-source')
  threads.append(threading.Thread(target=cloud_reader,args=(server,),daemon=True))
  threads[-1].start()
  deadline=float('inf') if args.seconds==0 else time.monotonic()+args.seconds;pending=None;last_cloud=-1.;first=True;last_metrics=0.
  while time.monotonic()<deadline and not rospy.is_shutdown() and not manual_stop_requested:
   if iproc.poll() is not None:raise RuntimeError('IMU worker ended unexpectedly')
   if not errors.empty():raise RuntimeError(errors.get())
   if not (lpub.get_num_connections() and ipub.get_num_connections()):time.sleep(.01);continue
   if pending is None:
    try:meta,raw,arrived=clouds.get(timeout=.1)
    except queue.Empty:continue
    try:
     convert_begin=time.monotonic()
     b,start,end,removed=convert_cloud(meta,raw,args.point_time_unit,args.header_reference)
     meta['queue_wait_s']=convert_begin-arrived
     meta['convert_s']=time.monotonic()-convert_begin
     meta['converted_at']=time.monotonic()
     if start<=last_cloud:raise ValueError('Nonincreasing cloud stamp')
     pending=(meta,b,start,end,arrived)
    except ValueError as e:
     stats['cloud_rejected']+=1;key=str(e);stats['rejection_reasons'][key]=stats['rejection_reasons'].get(key,0)+1;continue
   meta,b,start,end,arrived=pending
   if stale_cloud(time.time(),start):
    stats['cloud_stale_dropped']+=1;pending=None;continue
   if time.monotonic()-arrived>1.:stats['cloud_missing_imu']+=1;stats['cloud_imu_timeout']+=1;pending=None;continue
   with lock:
    if not imus or imus[-1][0]<end+.005:ready=False
    elif first and imus[0][0]>start:ready=False;stats['cloud_missing_imu']+=1;stats['cloud_imu_warmup_skipped']+=1;pending=None
    else:
     ready=True;batch=[]
     while imus and imus[0][0]<=end+.005:
      sample=imus.popleft()
      if sample[0]>=start-.2 or not first:batch.append(sample[1])
   if not ready:time.sleep(.002);continue
   if not batch:stats['cloud_missing_imu']+=1;stats['cloud_imu_empty_batch']+=1;pending=None;continue
   m=PointCloud2();m.header.stamp=rospy.Time.from_sec(start);m.header.frame_id='xt16_candidate';m.fields=fields;m.height=1;m.width=len(b);m.point_step=26;m.row_step=len(b)*26;m.is_dense=True;m.data=b.tobytes()
   pub_start=time.monotonic();source_age=time.time()-start
   stages=dict(queue_wait_s=meta['queue_wait_s'],convert_s=meta['convert_s'],coverage_and_schedule_s=pub_start-meta['converted_at'],stamp=start,driver_callback_age_s=meta['receipt']-(meta['stamp_sec']+meta['stamp_nanosec']*1e-9),ipc_age_s=meta['bridge_received']-meta['receipt'],bridge_wait_s=pub_start-arrived,scan_span_s=end-start)
   lpub.publish(m)
   if first:time.sleep(.05)
   cloud_timing.write(json.dumps(dict(updated=time.time(),source_age_s=source_age,publish_s=time.monotonic()-pub_start,queue=clouds.qsize(),**stages))+'\n')
   if time.monotonic()-last_metrics>1:
    if args.imu_source=='ros2':
     try:stats['max_receipt_tick_residual_ms']=json.loads((out/'imu_health.json').read_text())['max_receipt_tick_residual_ms']
     except (OSError,ValueError,KeyError):pass
    health=dict(updated=time.time(),cloud_source_age_s=source_age,publish_duration_s=time.monotonic()-pub_start,cloud_queue=clouds.qsize(),cloud_queue_dropped=stats['cloud_queue_dropped'],cloud_stale_dropped=stats['cloud_stale_dropped'],imu_buffer=len(imus),imu_latest_age_s=time.time()-batch[-1].header.stamp.to_sec(),cloud_published=stats['cloud_published'],tick_residual_max_ms=stats['max_receipt_tick_residual_ms'])
    tmp=out/'live_health.tmp';tmp.write_text(json.dumps(health));tmp.replace(out/'live_health.json');last_metrics=time.monotonic()
   stats['cloud_published']+=1;stats['max_cloud_receipt_age_ms']=max(stats['max_cloud_receipt_age_ms'],(time.time()-meta['receipt'])*1000)
   last_cloud=start;first=False;pending=None
  # Freeze intake before waiting for the algorithm to finish its last updates.
  stop.set()
  time.sleep(1)
except Exception as e:failure=str(e)
finally:
 stop.set()
 for c in children:
  if c.poll() is None:
   import signal
   os.killpg(c.pid,signal.SIGTERM)
 for c in children:
  try:c.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(c.pid,signal.SIGKILL);c.wait()
 for t in locals().get('threads',[]):t.join(timeout=1)
 for f in handles:f.close()
 if 'server' in locals():server.close()
 sub.unregister();rospy.signal_shutdown('Diagnostic finished');odomlog.close();stats['duplicate_ticks_dropped']=clock.duplicates;stats['tick_anchor']=clock.anchor;stats['failure']=failure
 if args.imu_source=='ros2' and (out/'imu_summary.json').exists():
  imu_stats=json.loads((out/'imu_summary.json').read_text())
  for key in ('duplicate_ticks_dropped','tick_anchor','max_receipt_tick_residual_ms'):stats[key]=imu_stats[key]
  stats['imu_worker_failure']=imu_stats['failure']
 (out/'summary.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats,indent=2))
if failure or stats['cloud_published']<50 or stats['odometry_count']<50 or stats['nonfinite_odometry']:raise SystemExit(1)
