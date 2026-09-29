#!/usr/bin/env python3
"""One supervised Nav2 goal, with an explicit execute flag and laptop lease.
No background/autostart movement. SportClient lives in a separate watchdog process.
"""
import argparse,fcntl,json,math,os,signal,subprocess,sys,threading,time
from pathlib import Path
from mapping_session import current_mapping_run
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose,FollowPath
from nav_msgs.msg import Odometry,OccupancyGrid
from geometry_msgs.msg import Twist
from path_refresh import needs_refresh
from terminal_control import TerminalAlignment,PositionRecoveryRequired
from staged_heading import HeadingAlignment,path_heading
from callback_drain import drain_ready
from heading_guard import is_level
from motion_policy import check_health,check_command,check_pose,swept_clear
ROOT=Path('/home/unitree/fast_livo2_port/build1');SHM=Path('/dev/shm/go2w_nav')
p=argparse.ArgumentParser();p.add_argument('--forward',type=float,default=.5);p.add_argument('--left',type=float,default=0);p.add_argument('--execute',action='store_true');p.add_argument('--output',required=True);p.add_argument('--floor',action='store_true');p.add_argument('--map-goal',action='store_true');p.add_argument('--yaw',type=float);p.add_argument('--named-goal');a=p.parse_args()
if not all(math.isfinite(v) for v in (a.forward,a.left)) or (not a.floor and not .1<=math.hypot(a.forward,a.left)<=2) or (a.floor and math.hypot(a.forward,a.left)>160):
 p.error('short goal 0.1–2m; floor relative displacement <=160m')
if (a.map_goal or a.named_goal) and not a.floor:p.error('map/named goals require floor mode')
if a.yaw is not None and not math.isfinite(a.yaw):p.error('yaw must be finite')
if a.floor and (ROOT/'navigation_profile').read_text().strip()!='floor':raise SystemExit('Select floor profile first')
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
  if pose==cur:return  # Duplicate snapshot is not a new measurement; do not refresh receipt.
  large=pose is not None and abs(math.atan2(math.sin(cur[2]-pose[2]),math.cos(cur[2]-pose[2])))>.20
  history=None;level=False
  if large:
   im=json.loads((SHM/'imu_health.json').read_text())
   if im.get('fault') or not 0<=time.time()-im['receipt']<.4:raise ValueError('IMU unavailable for heading verification')
   history=im.get('history',[])
   oldq=pose_m.pose.pose.orientation
   level=is_level((q.x,q.y,q.z,q.w)) and is_level((oldq.x,oldq.y,oldq.z,oldq.w))
  evidence=check_pose(pose,cur,history,level)
  if evidence:trace.write(json.dumps(dict(event='imu_verified_heading',t=time.time(),**evidence))+'\n');trace.flush()
  pose=cur;pose_m=m;received=time.monotonic()
 except Exception as e:
  fault=str(e)
  trace.write(json.dumps(dict(event='odometry_rejected',t=time.time(),previous=pose,candidate=locals().get('cur'),reason=fault))+'\n');trace.flush()
def cmd(m):
 global command,cmd_time,fault
 if any(abs(v)>1e-6 for v in (m.linear.z,m.angular.x,m.angular.y)):fault='unsupported command axes'
 now=time.monotonic()
 if cmd_time:trace.write(json.dumps(dict(event='command_interval',t=time.time(),dt=now-cmd_time))+'\n')
 command=(m.linear.x,m.linear.y,m.angular.z);cmd_time=now
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
guard=None;fh=None;handle=None;result_future=None;capture_run=None;trace=(out/'trace.jsonl').open('w');result=dict(execute=a.execute,success=False,ground_truth=None,floor=a.floor,replans=0);motion_limit=1800 if a.floor else 60
def service_callbacks(timeout):
 rclpy.spin_once(node,timeout_sec=timeout)
 drain_ready(lambda:rclpy.spin_once(node,timeout_sec=0.),time.monotonic)
def basic():
 if stop.is_set():raise RuntimeError('operator stop or laptop disconnected')
 if time.monotonic()-lease[0]>1.:raise RuntimeError('laptop heartbeat expired')
 if fault:raise RuntimeError(fault)
 if capture_run and current_mapping_run(ROOT)!=capture_run:raise RuntimeError('mapping session changed')
def healthy():
 basic();check_health(json.loads((SHM/'adapter_status.json').read_text()),time.time())
 im=json.loads((SHM/'imu_health.json').read_text())
 if im.get('fault') or not 0<=time.time()-im['receipt']<.4 or not 0<=time.time()-im['stamp']<.4:raise RuntimeError('IMU unhealthy: '+str({k:v for k,v in im.items() if k!='history'}))
 if pose is None or time.monotonic()-received>.85 or not 0<=time.time()-pose[3]<.85:raise RuntimeError('odometry stale')
 if grid is None or time.monotonic()-grid_time>2.5:raise RuntimeError('local costmap stale')
def wait(f,seconds=8,check=basic):
 end=time.monotonic()+seconds
 while not f.done():
  if time.monotonic()>end:raise TimeoutError('Nav2 action timeout')
  service_callbacks(.05);check()
 return f.result()
def transmit(v,phase):
 healthy();v=check_command(v,0.,.2 if a.floor else .1);swept_clear(grid,pose,v)
 if guard.poll() is not None:raise RuntimeError('Motion watchdog exited')
 msg=dict(sent_monotonic=time.monotonic(),vx=v[0],vy=v[1],yaw_rate=v[2])
 guard.stdin.write(json.dumps(msg)+'\n');guard.stdin.flush()
 trace.write(json.dumps(dict(t=time.time(),pose=pose,command=msg,execute=a.execute,phase=phase,pose_age_s=time.time()-pose[3],command_age_s=(time.monotonic()-cmd_time if phase in ('FollowPath','ApproachPath') else 0.),command_source=('nav2' if phase in ('FollowPath','ApproachPath') else 'supervisor')))+'\n');trace.flush()
def hold_check():
 healthy();transmit((0.,0.,0.),'controller_transition')
def final_alignment():
 if handle and handle.accepted:wait(handle.cancel_goal_async(),seconds=3,check=hold_check)
 alignment=TerminalAlignment(target,target_yaw,time.monotonic())
 end=time.monotonic()+(35 if a.execute else 5)
 while time.monotonic()<end:
  service_callbacks(.04);healthy()
  try:v,done=alignment.step(pose,time.monotonic())
  except PositionRecoveryRequired:
   transmit((0.,0.,0.),'position_recovery_stop');return None
  transmit(v,alignment.phase)
  if done:return True
 if not a.execute:return False
 raise RuntimeError('terminal alignment deadline')
def staged_path_restart(align=True):
 global handle,result_future,command,cmd_time,controller_id,active_ros_path
 # End the old DWB action before emitting supervisor rotation or consuming a new command.
 if handle and handle.accepted:
  wait(handle.cancel_goal_async(),seconds=3,check=hold_check)
  old=wait(result_future,seconds=3,check=hold_check)
  if old.status not in (4,5):raise RuntimeError('Controller did not cancel cleanly for staged alignment')
 def fresh_path():
  g.pose.header.stamp=node.get_clock().now().to_msg()
  ph=wait(planner.send_goal_async(g),check=hold_check)
  if not ph.accepted:raise RuntimeError('Staged planner rejected goal')
  rr=wait(ph.get_result_async(),check=hold_check)
  if rr.status!=4 or len(rr.result.path.poses)<2:raise RuntimeError('No valid staged path')
  ep=rr.result.path.poses[-1].pose.position
  if math.hypot(ep.x-target[0],ep.y-target[1])>.08:raise RuntimeError('Staged endpoint differs from target')
  return rr.result.path
 active_ros_path=fresh_path()
 points=[(p.pose.position.x,p.pose.position.y) for p in active_ros_path.poses]
 if align and math.hypot(pose[0]-target[0],pose[1]-target[1])>.08:
  h=HeadingAlignment(path_heading(points,pose),pose,time.monotonic())
  trace.write(json.dumps(dict(event='initial_heading_target',yaw=h.yaw,pose=pose,t=time.time()))+'\n');trace.flush()
  while True:
   service_callbacks(.04);healthy()
   v,done=h.step(pose,time.monotonic());transmit(v,h.phase)
   if done or not a.execute:break
  # Wheel-legged turns translate: plan again from the resulting measured position.
  active_ros_path=fresh_path()
 controller_id='ApproachPath' if math.hypot(pose[0]-target[0],pose[1]-target[1])<=.8 else 'FollowPath'
 fg=FollowPath.Goal();fg.path=active_ros_path;fg.controller_id=controller_id
 handle=wait(controller.send_goal_async(fg),seconds=3,check=hold_check)
 if not handle.accepted:raise RuntimeError('Controller rejected staged path')
 result_future=handle.get_result_async();command=None;deadline=time.monotonic()+3
 while time.monotonic()<deadline:
  service_callbacks(.02);hold_check()
  if command is None:continue
  candidate=check_command(command,time.monotonic()-cmd_time,.2)
  if controller_id!='ApproachPath' or (candidate[0]<=.080000001 and abs(candidate[2])<=.250000001):return
  command=None
 raise RuntimeError('No bounded fresh command after staged alignment')
try:
 print('Checking fresh inputs and stationary start...',flush=True)
 capture_run=current_mapping_run(ROOT);result['mapping_run']=capture_run
 end=time.monotonic()+12;stable=[];startup_error='waiting for pose/costmap'
 while time.monotonic()<end:
  service_callbacks(.05)
  # Allow startup delivery; never open the actuation guard during this phase.
  if stop.is_set() or fault:basic()
  try:healthy()
  except (ValueError,RuntimeError,FileNotFoundError,KeyError) as e:startup_error=str(e);stable=[];continue
  stable.append(pose);stable=[v for v in stable if pose[3]-v[3]<3.5]
  if len(stable)>=5 and stable[-1][3]-stable[0][3]>=3:
   if max(v[0] for v in stable)-min(v[0] for v in stable)<.03 and max(v[1] for v in stable)-min(v[1] for v in stable)<.03 and max(abs(math.atan2(math.sin(v[2]-pose[2]),math.cos(v[2]-pose[2]))) for v in stable)<.04:break
 else:raise RuntimeError('No fresh stationary start within 12s: '+startup_error)
 start=pose;result['start']=start;c,s=math.cos(start[2]),math.sin(start[2]);target=(start[0]+c*a.forward-s*a.left,start[1]+s*a.forward+c*a.left)
 target_yaw=start[2] if a.yaw is None else a.yaw
 if a.map_goal:target=(a.forward,a.left)
 if a.named_goal:
  places=json.loads((ROOT/'navigation_places.json').read_text())
  if places['mapping_run']!=capture_run:raise RuntimeError('Recorded places belong to a different mapping session')
  place=places['places'][a.named_goal];target=tuple(place['pose'][:2]);target_yaw=place['pose'][2]
 if not all(math.isfinite(v) for v in (*target,target_yaw)):raise RuntimeError('Nonfinite target')
 if a.floor and (max(abs(target[0]),abs(target[1]))>90 or math.hypot(*target)>90):raise RuntimeError('Floor target outside mapped workspace radius 90m')
 result['target']=target;result['target_yaw']=target_yaw
 if not planner.wait_for_server(timeout_sec=3) or not controller.wait_for_server(timeout_sec=3):raise RuntimeError('Nav2 unavailable')
 healthy();g=ComputePathToPose.Goal();g.planner_id='GridBased';g.pose.header.frame_id='camera_init';g.pose.header.stamp=node.get_clock().now().to_msg();g.pose.pose.position.x,g.pose.pose.position.y=target;g.pose.pose.orientation.z=math.sin(target_yaw/2);g.pose.pose.orientation.w=math.cos(target_yaw/2)
 pg=wait(planner.send_goal_async(g),check=healthy)
 if not pg.accepted:raise RuntimeError('Planner rejected goal')
 pr=wait(pg.get_result_async(),check=healthy)
 if pr.status!=4 or len(pr.result.path.poses)<2:raise RuntimeError('No valid path')
 result['path']=[[v.pose.position.x,v.pose.position.y] for v in pr.result.path.poses]
 # Refuse a planner tolerance endpoint that already differs materially from requested target.
 if math.hypot(result['path'][-1][0]-target[0],result['path'][-1][1]-target[1])>.08:raise RuntimeError('Planned endpoint differs from requested goal')
 swept_clear(grid,pose,(0.,0.,0.));command=None;cmd_time=0.
 controller_id='ApproachPath' if a.floor and math.hypot(pose[0]-target[0],pose[1]-target[1])<=.8 else 'FollowPath'
 active_ros_path=pr.result.path
 fg=FollowPath.Goal();fg.path=pr.result.path;fg.controller_id=controller_id;handle=wait(controller.send_goal_async(fg),check=healthy)
 if not handle.accepted:raise RuntimeError('Controller rejected path')
 result_future=handle.get_result_async()
 # Wait for a newly generated command after accepting our path.
 position_ready=a.floor and math.hypot(pose[0]-target[0],pose[1]-target[1])<=.08
 command=(0.,0.,0.) if position_ready else None;cmd_time=time.monotonic();end=time.monotonic()+2
 while command is None and time.monotonic()<end:service_callbacks(.05);healthy()
 if command is None:raise RuntimeError('No controller command')
 v=check_command(command,time.monotonic()-cmd_time,.2 if a.floor else .1);swept_clear(grid,pose,v)
 fh=(out/'guard.log').open('w');env={k:os.environ[k] for k in ('HOME','USER','LANG') if k in os.environ};env['PATH']='/usr/bin:/bin'
 guard=subprocess.Popen([str(ROOT/'navigation/build/sport_guard'),'eth0',('--execute-floor' if a.execute else '--preview-floor') if a.floor else ('--execute-nav' if a.execute else '--preview-nav')],stdin=subprocess.PIPE,stdout=fh,stderr=subprocess.STDOUT,text=True,env=env)
 # SDK/DDS initialization can exceed the 150 ms command lease. Do not queue
 # commands before the guard has announced readiness; keep checking live inputs.
 ready_deadline=time.monotonic()+4.
 while True:
  if guard.poll() is not None:raise RuntimeError('Motion watchdog exited during initialization')
  if '"ready":true' in (out/'guard.log').read_text():break
  if time.monotonic()>ready_deadline:raise RuntimeError('Motion watchdog initialization timed out')
  service_callbacks(.02);healthy()
 command=(0.,0.,0.) if position_ready else None;cmd_time=time.monotonic();fresh_deadline=time.monotonic()+1.
 while command is None and time.monotonic()<fresh_deadline:
  service_callbacks(.02);healthy()
 if command is None:raise RuntimeError('No fresh command after watchdog initialization')
 if a.floor and not position_ready:staged_path_restart()
 print('Following path: '+('REAL MOTION' if a.execute else 'DRY RUN, no SportClient calls'),flush=True)
 end=time.monotonic()+(motion_limit if a.execute else 8 if a.floor else 5);last_print=0
 active_path=[(p.pose.position.x,p.pose.position.y) for p in active_ros_path.poses];accepted_pose=pose[:2]
 replan_send=None;replan_result=None;replace_send=None;next_plan=time.monotonic()+2.;plan_started=0.;pending_path=None
 while time.monotonic()<end:
  service_callbacks(.04);healthy()
  if guard.poll() is not None:raise RuntimeError('Motion watchdog exited')
  if (math.hypot(pose[0],pose[1])>92 if a.floor else math.hypot(pose[0]-start[0],pose[1]-start[1])>3):raise RuntimeError('Trial radius exceeded')
  if a.floor and math.hypot(pose[0]-target[0],pose[1]-target[1])<=.08 and replan_send is None and replan_result is None and replace_send is None:
   result['terminal_started']=True
   done=final_alignment()
   if done is None:
    recoveries=result.get('position_recoveries',0)
    if recoveries>=2:raise RuntimeError('Terminal position recovery limit reached')
    result['position_recoveries']=recoveries+1
    trace.write(json.dumps(dict(event='terminal_position_replan',pose=pose,t=time.time(),attempt=recoveries+1))+'\n');trace.flush()
    staged_path_restart()
    active_path=[(p.pose.position.x,p.pose.position.y) for p in active_ros_path.poses];accepted_pose=pose[:2];next_plan=time.monotonic()+2.
    continue
   result['reason']='controller reached goal' if done else 'terminal dry run passed'
   if not a.execute:result['success']=True
   break
  if a.floor and controller_id=='FollowPath' and math.hypot(pose[0]-target[0],pose[1]-target[1])<=.8 and replan_send is None and replan_result is None and replace_send is None:
   transmit((0.,0.,0.),'switching_to_approach')
   # Finish the old action before accepting commands from the shared Twist topic.
   wait(handle.cancel_goal_async(),seconds=3,check=hold_check)
   old_result=wait(result_future,seconds=3,check=hold_check)
   if old_result.status not in (4,5):raise RuntimeError('Old controller did not finish cleanly')
   controller_id='ApproachPath';fg=FollowPath.Goal();fg.path=active_ros_path;fg.controller_id=controller_id
   handle=wait(controller.send_goal_async(fg),seconds=3,check=hold_check)
   if not handle.accepted:raise RuntimeError('Approach controller rejected path')
   result_future=handle.get_result_async();command=None;deadline=time.monotonic()+3
   while time.monotonic()<deadline:
    service_callbacks(.02);hold_check()
    if command is None:continue
    candidate=check_command(command,time.monotonic()-cmd_time,.2)
    if candidate[0]<=.080000001 and abs(candidate[2])<=.250000001:break
    trace.write(json.dumps(dict(event='approach_command_held',t=time.time(),command=candidate))+'\n');trace.flush()
    command=None
   else:raise RuntimeError('Approach controller did not produce a bounded command within 3s')
   trace.write(json.dumps(dict(event='approach_controller_selected',t=time.time()))+'\n')
  if result_future.done() and replace_send is None:
   res=result_future.result();result['controller_status']=res.status
   if res.status!=4:raise RuntimeError('Controller failed/canceled: '+str(res.status))
   result['reason']='controller reached goal';break
  # Replanning is asynchronous: keep checking the lease and live velocity every cycle.
  if a.floor:
   now=time.monotonic()
   if (replan_send is not None or replan_result is not None or replace_send is not None) and now-plan_started>4.:raise RuntimeError('Replanning deadline exceeded')
   if replace_send is not None and replace_send.done():
    replacement=replace_send.result();replace_send=None
    if not replacement.accepted:raise RuntimeError('Controller rejected replanned path')
    handle=replacement;result_future=handle.get_result_async();result['replans']+=1;next_plan=now+2.
    active_ros_path=pending_path;active_path=[(p.pose.position.x,p.pose.position.y) for p in pending_path.poses];accepted_pose=pose[:2]
    trace.write(json.dumps(dict(event='replanned',t=time.time(),points=len(pending_path.poses)))+'\n')
   if replan_result is not None and replan_result.done():
    updated=replan_result.result();replan_result=None
    if updated.status!=4 or len(updated.result.path.poses)<2:raise RuntimeError('Replanning found no path')
    pending_path=updated.result.path;endpoint=pending_path.poses[-1].pose.position
    if math.hypot(endpoint.x-target[0],endpoint.y-target[1])>.08:raise RuntimeError('Replanned endpoint differs from goal')
    candidate=[(p.pose.position.x,p.pose.position.y) for p in pending_path.poses]
    if needs_refresh(candidate,active_path,pose,accepted_pose):
     fg=FollowPath.Goal();fg.path=pending_path;fg.controller_id=controller_id;replace_send=controller.send_goal_async(fg)
    else:
     next_plan=now+2.
     trace.write(json.dumps(dict(event='unchanged_path_kept',t=time.time()))+'\n')
   if replan_send is not None and replan_send.done():
    ph=replan_send.result();replan_send=None
    if not ph.accepted:raise RuntimeError('Planner rejected replan')
    replan_result=ph.get_result_async()
   if replan_send is None and replan_result is None and replace_send is None and now>=next_plan and math.hypot(pose[0]-target[0],pose[1]-target[1])>.5:
    g.pose.header.stamp=node.get_clock().now().to_msg();replan_send=planner.send_goal_async(g);plan_started=now;next_plan=now+2.
  v=check_command(command,time.monotonic()-cmd_time,.2 if a.floor else .1)
  if controller_id=='ApproachPath' and (v[0]>.080000001 or abs(v[2])>.250000001):raise RuntimeError('Approach command exceeds phase limits')
  transmit(v,controller_id)
  if time.monotonic()-last_print>1:
   print(json.dumps(dict(distance_to_goal=math.hypot(pose[0]-target[0],pose[1]-target[1]),vx=v[0],yaw_rate=v[2],execute=a.execute)),flush=True);last_print=time.monotonic()
 else:
  if a.execute:raise RuntimeError(str(motion_limit)+'s motion deadline exceeded')
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
 if 'replace_send' in locals() and replace_send is not None:
  try:
   deadline=time.monotonic()+2
   while not replace_send.done() and time.monotonic()<deadline:service_callbacks(.05)
   if replace_send.done() and replace_send.result().accepted:replace_send.result().cancel_goal_async()
  except Exception:pass
 if handle and handle.accepted:
  try:
   f=handle.cancel_goal_async();deadline=time.monotonic()+2
   while not f.done() and time.monotonic()<deadline:service_callbacks(.05)
  except Exception:pass
 if a.execute and result.get('reason')=='controller reached goal':
  settled=[];deadline=time.monotonic()+2
  try:
   while time.monotonic()<deadline:
    service_callbacks(.05);healthy();settled.append(pose)
   err=math.hypot(pose[0]-target[0],pose[1]-target[1]);dyaw=abs(math.atan2(math.sin(pose[2]-target_yaw),math.cos(pose[2]-target_yaw)))
   result['estimated_error_m']=err;result['estimated_yaw_error_rad']=dyaw
   recent=[v for v in settled if v[3]>=pose[3]-1.]
   result['success']=guard.returncode==0 and err<=.08 and dyaw<=.15 and len(recent)>=3 and max(v[0] for v in recent)-min(v[0] for v in recent)<.03 and max(v[1] for v in recent)-min(v[1] for v in recent)<.03
   if not result['success']:result['reason']='Stopped outside goal tolerance or not settled'
  except Exception as e:result['success']=False;result['reason']='Post-stop verification: '+str(e)
 if guard and guard.returncode!=0:result['success']=False
 result['last_pose']=pose;(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 info.update(running=False,result=result['reason'],success=result['success']);state.write_text(json.dumps(info));trace.close();planner.destroy();controller.destroy();node.destroy_node();rclpy.shutdown()
raise SystemExit(0 if result['success'] else 1)
