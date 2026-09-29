#!/usr/bin/env python3
"""Short supervised forward point trial; default preview, not a navigation stack."""
import argparse,json,math,os,signal,subprocess,time,threading
from pathlib import Path
# Keep small point-cloud checks from spawning many BLAS worker threads.
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_THREAD_LIMIT"]="2"
import numpy as np,rospy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu,PointCloud2
from point_policy import velocity, endpoint_metrics
ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--distance',type=float,default=.3);ap.add_argument('--execute',action='store_true');ap.add_argument('--startup-test',action='store_true',help='0.10 m/s cap, two-second duration');ap.add_argument('--point-test',action='store_true',help='0.10 m/s bounded forward goal, maximum eight seconds');args=ap.parse_args()
if args.startup_test and args.point_test:ap.error('choose only one test mode')
if not math.isfinite(args.distance) or not .1<=args.distance<=.5:ap.error('distance must be 0.1–0.5 metres')
out=Path(args.output);out.mkdir(exist_ok=False);log=(out/'trace.jsonl').open('w')
rospy.init_node('go2w_livo_short_point_trial');lock=threading.Lock();s={'pose':None,'odom_received':0.,'cloud_received':0.,'imu_received':0.,'clear':False,'fault':None,'imu_stamp':None,'odom_stamp':None,'blocked_points':None}
R=np.array(rospy.get_param('/go2w_lio/extrin_calib/extrinsic_R')).reshape(3,3);T=np.array(rospy.get_param('/go2w_lio/extrin_calib/extrinsic_T'))
def odom(m):
 p=m.pose.pose.position;q=m.pose.pose.orientation;t=m.header.stamp.to_sec();now=time.monotonic();v=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]
 with lock:
  if m.header.frame_id!='camera_init' or not np.isfinite(v).all() or abs(sum(x*x for x in v[3:])-1)>.02:s['fault']='bad odometry';return
  if s['odom_stamp'] is not None and t<=s['odom_stamp']:s['fault']='odometry stamp rollback';return
  if s['pose'] is not None and math.hypot(p.x-s['pose'][0],p.y-s['pose'][1])>.15:s['fault']='odometry position jump';return
  s['pose']=(p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)));s['odom_received']=now;s['odom_stamp']=t

def imu(m):
 t=m.header.stamp.to_sec()
 with lock:
  if s['imu_stamp'] is not None and (t<=s['imu_stamp'] or t-s['imu_stamp']>.020001):s['fault']='IMU input discontinuity'
  s['imu_stamp']=t;s['imu_received']=time.monotonic()
def cloud(m):
 try:
  fields={f.name:f for f in m.fields}
  if any(fields[k].datatype!=7 for k in ['x','y','z']):raise ValueError('XYZ type')
  dt=np.dtype({'names':['x','y','z'],'formats':[('>' if m.is_bigendian else '<')+'f4']*3,'offsets':[fields[k].offset for k in ['x','y','z']],'itemsize':m.point_step})
  a=np.ndarray((m.height,m.width),dtype=dt,buffer=m.data,strides=(m.row_step,m.point_step));p=np.column_stack([a[k].ravel() for k in ['x','y','z']]);p=p[np.isfinite(p).all(1)];p=p@R.T+T
  if len(p)<500:raise ValueError('insufficient point coverage')
  n=int(((p[:,0]>.35)&(p[:,0]<1.1)&(abs(p[:,1])<.4)&(p[:,2]>-.1)&(p[:,2]<.8)).sum())
  with lock:s['cloud_received']=time.monotonic();s['clear']=n==0;s['blocked_points']=n
 except Exception as e:
  with lock:s['fault']='cloud: '+str(e)
rospy.Subscriber('/go2w_lio/odometry',Odometry,odom,queue_size=10);rospy.Subscriber('/go2w_lio/imu',Imu,imu,queue_size=2000);rospy.Subscriber('/go2w_lio/points',PointCloud2,cloud,queue_size=1,buff_size=8*1024*1024)
stop=threading.Event()
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
failure_details=None;post_stop=[];motion_stop_reason=None;post_stop_fault=None
proc=None;reason='time limit';samples=0;start=None;feedback=[];fh=None
try:
 print('阶段1/3：检查传感器、前方点云与静止起点；请停止遥控操作。',flush=True)
 deadline=time.monotonic()+15;stable=[]
 while time.monotonic()<deadline and not stop.is_set():
  with lock:v=dict(s)
  now=time.monotonic()
  if v['fault']:raise RuntimeError(v['fault'])
  if v['pose'] and now-v['odom_received']<.85 and now-v['cloud_received']<.4 and now-v['imu_received']<.4:
   stable.append((now,v['pose']));stable=[x for x in stable if now-x[0]<3.5]
   if len(stable)>20 and now-stable[0][0]>3:
    pts=np.array([x[1] for x in stable]);
    if np.max(np.ptp(pts[:,:2],axis=0))<.03 and np.ptp(np.unwrap(pts[:,2]))<.04:start=tuple(np.median(pts,axis=0));break
  time.sleep(.05)
 if start is None:raise RuntimeError('No stable fresh starting pose')
 if not v['clear']:raise RuntimeError('Front corridor blocked: '+str(v['blocked_points']))
 print('阶段2/3：开始自动运动，请勿遥控移动（紧急接管除外）。' if args.execute else '阶段2/3：仅预演，不发送运动指令。',flush=True)
 fh=(out/'guard.log').open('w');cmd=[str(Path(__file__).parent/'build/sport_guard'),'eth0']+(['--execute-point' if args.execute else '--preview-point'] if args.point_test else ['--execute-startup'] if args.execute and args.startup_test else ['--execute'] if args.execute else ['--preview-startup'] if args.startup_test else [])
 env={k:os.environ[k] for k in ('HOME','USER','LANG') if k in os.environ};env['PATH']='/usr/bin:/bin'
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=fh,stderr=subprocess.STDOUT,text=True,env=env)
 # 50cm at 0.10m/s needs startup margin: Python 8s, independent C++ guard 8.5s.
 # Timeout is a failed reach, never silently retried.
 end=time.monotonic()+(2 if args.startup_test else 8 if args.point_test else 12);arrival_since=None
 while time.monotonic()<end and not stop.is_set():
  now=time.monotonic()
  with lock:v=dict(s)
  if v['fault']:raise RuntimeError(v['fault'])
  ages={k:now-v[k+'_received'] for k in ('odom','cloud','imu')}
  if ages['odom']>.85 or ages['cloud']>.4 or ages['imu']>.4:
   failure_details=dict(monotonic=now,wall_time=time.time(),ages=ages,odom_stamp=v['odom_stamp'],imu_stamp=v['imu_stamp'])
   raise RuntimeError('stale sensor input: '+json.dumps(ages))
  if not v['clear']:raise RuntimeError('front corridor blocked')
  if proc.poll() is not None:raise RuntimeError('sport guard exited')
  vx,w,arrived=velocity(start,v['pose'],args.distance,.1 if (args.startup_test or args.point_test) else .05,hold_speed=args.point_test)
  if arrived and args.point_test:
   reason='target stop requested';break
  if arrived:
   if arrival_since is None:arrival_since=now
   if now-arrival_since>.8:reason='goal reached';break
  else:arrival_since=None
  msg={'sent_monotonic':now,'vx':vx,'vy':0.,'yaw_rate':w};proc.stdin.write(json.dumps(msg)+'\n');proc.stdin.flush();samples+=1
  log.write(json.dumps(dict(t=now,wall_time=time.time(),ages=ages,pose=v['pose'],start=start,command=msg,execute=args.execute,blocked_points=v['blocked_points']))+'\n');log.flush();time.sleep(.05)
 if stop.is_set():reason='interrupted'
except Exception as e:reason=str(e)
finally:
 print('阶段3/3：结束指令，检查停车反馈；请保持原位等待测量。',flush=True)
 # 保留导致停止的原始原因，不能被停车后观察失败覆盖。
 motion_stop_reason=reason
 if proc is not None:
  proc.stdin.close()
  try:proc.wait(timeout=3)
  except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
 if fh:fh.close()
 if args.point_test and args.execute and proc is not None:
  # Observe only after EOF caused StopMove; never send a restart during settling.
  settle_until=time.monotonic()+5.0;last_stamp=None
  while time.monotonic()<settle_until and not stop.is_set():
   with lock:v=dict(s)
   now=time.monotonic()
   if v['fault'] or now-v['odom_received']>.85:
    post_stop_fault=v['fault'] or 'stale post-stop odometry'
    if reason=='target stop requested':reason='post-stop feedback invalid'
    break
   if v['odom_stamp']!=last_stamp:
    post_stop.append(dict(t=now,pose=v['pose'],stamp=v['odom_stamp']));last_stamp=v['odom_stamp']
   time.sleep(.05)
  if reason=='target stop requested':
   if len(post_stop)<3:reason='insufficient post-stop feedback'
   else:
    final=post_stop[-1]['pose'];target=(start[0]+args.distance*math.cos(start[2]),start[1]+args.distance*math.sin(start[2]))
    error=math.hypot(final[0]-target[0],final[1]-target[1]);recent=np.array([x['pose'][:2] for x in post_stop[-3:]])
    reason='goal reached' if proc.returncode==0 and error<=.08 and np.max(np.ptp(recent,axis=0))<.03 else 'stopped outside goal tolerance or not settled'

 with lock:v=dict(s)
 # Median of the final three fresh poses suppresses a single-frame endpoint spike.
 estimated_endpoint=endpoint_metrics(start,tuple(np.median(np.array([x['pose'] for x in post_stop[-3:]]),axis=0)),args.distance) if start is not None and len(post_stop)>=3 else None
 result=dict(motion_stop_reason=motion_stop_reason,post_stop_fault=post_stop_fault,sensor_fault=v['fault'],estimated_endpoint=estimated_endpoint,ground_truth=None,motion_limit_s=8 if args.point_test else 2 if args.startup_test else 12,point_test=args.point_test,post_stop=post_stop,failure_details=failure_details,startup_test=args.startup_test,execute=args.execute,reason=reason,start=start,last_pose=v['pose'],commands=samples,guard_returncode=proc.returncode if proc else None,blocked_points=v['blocked_points'],distance=args.distance)
 (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));log.close()

raise SystemExit(0 if (reason=="goal reached" or (not args.execute and reason=="time limit")) and result["guard_returncode"]==0 else 1)
