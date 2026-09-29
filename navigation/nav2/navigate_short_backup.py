#!/usr/bin/env python3
"""One supervised Nav2 goal, with an explicit execute flag and laptop lease.
No background/autostart movement. SportClient lives in a separate watchdog process.
"""
import argparse,fcntl,json,math,os,signal,subprocess,sys,threading,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose,FollowPath
from nav_msgs.msg import Odometry,OccupancyGrid
from geometry_msgs.msg import Twist
from motion_policy import check_health,check_command,check_pose,swept_clear
ROOT=Path('/home/unitree/fast_livo2_port/build1');SHM=Path('/dev/shm/go2w_nav')
p=argparse.ArgumentParser();p.add_argument('--forward',type=float,default=.5);p.add_argument('--left',type=float,default=0);p.add_argument('--execute',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
if not all(math.isfinite(v) for v in (a.forward,a.left)) or not .1<=math.hypot(a.forward,a.left)<=2:
 p.error('goal distance must be 0.1–2m')
lock=(ROOT/'point_trial.lock').open('w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Another motion/plan trial owns the robot')
out=Path(a.output);out.mkdir(exist_ok=False)
def birth(pid):return Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()[19]
state=ROOT/'navigation_goal.json';info=dict(pid=os.getpid(),birth=birth(os.getpid()),run=out.name,execute=a.execute,running=True)
state.write_text(json.dumps(info))
stop=threading.Event();lease=[0.]
def heartbeats():
 for line in sys.stdin:
  if line.strip()=='HEARTBEAT':lease[0]=time.monotonic()
  else:stop.set();break
 stop.set()
threading.Thread(target=heartbeats,daemon=True).start()
rclpy.init();node=Node('go2w_supervised_navigation');pose=None;pose_m=None;received=0.;command=None;cmd_time=0.;grid=None;grid_time=0.;fault=None
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
def odom(m):
 global pose,pose_m,received,fault
 try:
  q=m.pose.pose.orientation;v=m.pose.pose.position;stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9
  if m.header.frame_id!='camera_init' or abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1)>.02:raise ValueError('odometry frame/quaternion')
  yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));cur=(v.x,v.y,yaw,stamp)
  check_pose(pose,cur);pose=cur;pose_m=m;received=time.monotonic()
 except Exception as e:fault=str(e)
def cmd(m):
 global command,cmd_time,fault
 if any(abs(v)>1e-6 for v in (m.linear.z,m.angular.x,m.angular.y)):fault='unsupported command axes'
 command=(m.linear.x,m.linear.y,m.angular.z);cmd_time=time.monotonic()
def costmap(m):
 global grid,grid_time,fault
 q=m.info.origin.orientation
 if m.header.frame_id!='camera_init' or abs(q.x)+abs(q.y)+abs(q.z)>1e-6 or m.info.resolution<=0 or len(m.data)!=m.info.width*m.info.height:
  fault='invalid local costmap';return
 grid=(m.data,m.info.width,m.info.height,m.info.resolution,m.info.origin.position.x,m.info.origin.position.y);grid_time=time.monotonic()
node.create_subscription(Odometry,'/go2w_nav/odom',odom,10)
node.create_subscription(Twist,'/go2w_nav/proposed_cmd_vel',cmd,1)
node.create_subscription(OccupancyGrid,'/local_costmap/costmap',costmap,1)
planner=ActionClient(node,ComputePathToPose,'compute_path_to_pose');controller=ActionClient(node,FollowPath,'follow_path')
guard=None;fh=None;handle=None;result_future=None;capture_run=None;trace=(out/'trace.jsonl').open('w');result=dict(execute=a.execute,success=False,ground_truth=None)
def basic():
 if stop.is_set():raise RuntimeError('operator stop or laptop disconnected')
 if time.monotonic()-lease[0]>1.:raise RuntimeError('laptop heartbeat expired')
 if fault:raise RuntimeError(fault)
 if capture_run and json.loads((ROOT/'continuous_capture.json').read_text())['run']!=capture_run:raise RuntimeError('mapping session changed')
def healthy():
 basic();check_health(json.loads((SHM/'adapter_status.json').read_text()),time.time())
 im=json.loads((SHM/'imu_health.json').read_text())
 if im.get('fault') or not 0<=time.time()-im['receipt']<.4 or not 0<=time.time()-im['stamp']<.4:raise RuntimeError('IMU unhealthy: '+str(im))
 if pose is None or time.monotonic()-received>.85 or not 0<=time.time()-pose[3]<.85:raise RuntimeError('odometry stale')
 if grid is None or time.monotonic()-grid_time>2.5:raise RuntimeError('local costmap stale')
def wait(f,seconds=8,check=basic):
 end=time.monotonic()+seconds
 while not f.done():
  if time.monotonic()>end:raise TimeoutError('Nav2 action timeout')
  rclpy.spin_once(node,timeout_sec=.05);check()
 return f.result()
try:
 print('Checking fresh inputs and stationary start...',flush=True)
 capture_run=json.loads((ROOT/'continuous_capture.json').read_text())['run'];result['mapping_run']=capture_run
 end=time.monotonic()+12;stable=[]
 while time.monotonic()<end:
  rclpy.spin_once(node,timeout_sec=.05)
  # Allow startup delivery; never open the actuation guard during this phase.
  if stop.is_set() or fault:basic()
  try:healthy()
  except (ValueError,RuntimeError,FileNotFoundError,KeyError):stable=[];continue
  stable.append(pose);stable=[v for v in stable if pose[3]-v[3]<3.5]
  if len(stable)>=5 and stable[-1][3]-stable[0][3]>=3:
   if max(v[0] for v in stable)-min(v[0] for v in stable)<.03 and max(v[1] for v in stable)-min(v[1] for v in stable)<.03 and max(abs(math.atan2(math.sin(v[2]-pose[2]),math.cos(v[2]-pose[2]))) for v in stable)<.04:break
 else:raise RuntimeError('No fresh stationary start within 12s')
 start=pose;result['start']=start;c,s=math.cos(start[2]),math.sin(start[2]);target=(start[0]+c*a.forward-s*a.left,start[1]+s*a.forward+c*a.left)
 result['target']=target
 if not planner.wait_for_server(timeout_sec=3) or not controller.wait_for_server(timeout_sec=3):raise RuntimeError('Nav2 unavailable')
 healthy();g=ComputePathToPose.Goal();g.planner_id='GridBased';g.pose.header.frame_id='camera_init';g.pose.header.stamp=node.get_clock().now().to_msg();g.pose.pose.position.x,g.pose.pose.position.y=target;g.pose.pose.orientation=pose_m.pose.pose.orientation
 pg=wait(planner.send_goal_async(g),check=healthy)
 if not pg.accepted:raise RuntimeError('Planner rejected goal')
 pr=wait(pg.get_result_async(),check=healthy)
 if pr.status!=4 or len(pr.result.path.poses)<2:raise RuntimeError('No valid path')
 result['path']=[[v.pose.position.x,v.pose.position.y] for v in pr.result.path.poses]
 # Refuse a planner tolerance endpoint that already differs materially from requested target.
 if math.hypot(result['path'][-1][0]-target[0],result['path'][-1][1]-target[1])>.08:raise RuntimeError('Planned endpoint differs from requested goal')
 swept_clear(grid,pose,(0.,0.,0.));command=None;cmd_time=0.
 fg=FollowPath.Goal();fg.path=pr.result.path;fg.controller_id='FollowPath';handle=wait(controller.send_goal_async(fg),check=healthy)
 if not handle.accepted:raise RuntimeError('Controller rejected path')
 result_future=handle.get_result_async()
 # Wait for a newly generated command after accepting our path.
 command=None;cmd_time=0.;end=time.monotonic()+2
 while command is None and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.05);healthy()
 if command is None:raise RuntimeError('No controller command')
 v=check_command(command,time.monotonic()-cmd_time);swept_clear(grid,pose,v)
 fh=(out/'guard.log').open('w');env={k:os.environ[k] for k in ('HOME','USER','LANG') if k in os.environ};env['PATH']='/usr/bin:/bin'
 guard=subprocess.Popen([str(ROOT/'navigation/build/sport_guard'),'eth0','--execute-nav' if a.execute else '--preview-nav'],stdin=subprocess.PIPE,stdout=fh,stderr=subprocess.STDOUT,text=True,env=env)
 print('Following path: '+('REAL MOTION' if a.execute else 'DRY RUN, no SportClient calls'),flush=True)
 end=time.monotonic()+(60 if a.execute else 5);last_print=0
 while time.monotonic()<end:
  rclpy.spin_once(node,timeout_sec=.04);healthy()
  if guard.poll() is not None:raise RuntimeError('Motion watchdog exited')
  if math.hypot(pose[0]-start[0],pose[1]-start[1])>3:raise RuntimeError('Trial radius exceeded')
  if result_future.done():
   res=result_future.result();result['controller_status']=res.status
   if res.status!=4:raise RuntimeError('Controller failed/canceled: '+str(res.status))
   result['reason']='controller reached goal';break
  v=check_command(command,time.monotonic()-cmd_time);swept_clear(grid,pose,v)
  msg=dict(sent_monotonic=time.monotonic(),vx=v[0],vy=v[1],yaw_rate=v[2]);guard.stdin.write(json.dumps(msg)+'\n');guard.stdin.flush()
  trace.write(json.dumps(dict(t=time.time(),pose=pose,command=msg,execute=a.execute))+'\n');trace.flush()
  if time.monotonic()-last_print>1:
   print(json.dumps(dict(distance_to_goal=math.hypot(pose[0]-target[0],pose[1]-target[1]),vx=v[0],yaw_rate=v[2],execute=a.execute)),flush=True);last_print=time.monotonic()
 else:
  if a.execute:raise RuntimeError('60s motion deadline exceeded')
  result['reason']='dry run passed';result['success']=True
except Exception as e:result['reason']=str(e)
finally:
 # Close motor command pipe BEFORE waiting for action cancellation or ROS shutdown.
 if guard:
  try:guard.stdin.close()
  except (BrokenPipeError,OSError):pass
  try:guard.wait(timeout=2)
  except subprocess.TimeoutExpired:guard.terminate();guard.wait(timeout=2)
  result['guard_returncode']=guard.returncode
 if fh:fh.close()
 if handle and handle.accepted:
  try:
   f=handle.cancel_goal_async();deadline=time.monotonic()+2
   while not f.done() and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
  except Exception:pass
 if a.execute and result.get('reason')=='controller reached goal':
  settled=[];deadline=time.monotonic()+2
  try:
   while time.monotonic()<deadline:
    rclpy.spin_once(node,timeout_sec=.05);healthy();settled.append(pose)
   err=math.hypot(pose[0]-target[0],pose[1]-target[1]);dyaw=abs(math.atan2(math.sin(pose[2]-start[2]),math.cos(pose[2]-start[2])))
   result['estimated_error_m']=err;result['estimated_yaw_error_rad']=dyaw
   recent=[v for v in settled if v[3]>=pose[3]-1.]
   result['success']=guard.returncode==0 and err<=.08 and dyaw<=.15 and len(recent)>=3 and max(v[0] for v in recent)-min(v[0] for v in recent)<.03 and max(v[1] for v in recent)-min(v[1] for v in recent)<.03
   if not result['success']:result['reason']='Stopped outside goal tolerance or not settled'
  except Exception as e:result['success']=False;result['reason']='Post-stop verification: '+str(e)
 if guard and guard.returncode!=0:result['success']=False
 result['last_pose']=pose;(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 info.update(running=False,result=result['reason'],success=result['success']);state.write_text(json.dumps(info));trace.close();planner.destroy();controller.destroy();node.destroy_node();rclpy.shutdown()
raise SystemExit(0 if result['success'] else 1)
