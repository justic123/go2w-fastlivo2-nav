"""Nav2 action -> guarded smoothed velocity. Default preview uses board guard without SDK."""
import json,time,math,sys,signal,fcntl,os
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import Odometry,OccupancyGrid
from geometry_msgs.msg import Twist,PoseStamped
from nav2_msgs.action import NavigateToPose,ComputePathToPose
from tf2_ros import Buffer,TransformListener
from guard_proxy import Guard
sys.path.insert(0,'/tmp/mppi_policy')
from motion_policy import swept_clear
from route_model import stationary,leg_timeout
root=Path(__file__).resolve().parent;current=json.loads((root/'current.json').read_text());state=Path('/state');target=json.loads((state/'accuracy_target.json').read_text());execute='--execute' in sys.argv
timeout_s=int(sys.argv[sys.argv.index('--timeout')+1]) if '--timeout' in sys.argv else 90
if not 10<=timeout_s<=1770:raise ValueError('Invalid execution deadline')
route_action='--route' in sys.argv
lock=(state/'motion.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
rclpy.init();n=Node('mppi_protected_action',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)]);buf=Buffer();listener=TransformListener(buf,n)
pose=None;grid=None;command=None;pose_received=0.;grid_received=0.;fault=None;stop_requested=False;history=[];goal=None;guard=None
result=dict(execute=execute,success=False,target=target,ground_truth=None)
# Retain recent global grids so a transient replan failure remains inspectable after stopping.
global_grids=[]
collision_snapshot=None
grid_metadata=None
def global_costs(m):
 global_grids.append(dict(receipt=time.time(),stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9,frame=m.header.frame_id,width=m.info.width,height=m.info.height,resolution=m.info.resolution,origin=[m.info.origin.position.x,m.info.origin.position.y],data=list(m.data)))
 global_grids[:]=global_grids[-8:]
n.create_subscription(OccupancyGrid,'/global_costmap/costmap',global_costs,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
def angle(x):return math.atan2(math.sin(x),math.cos(x))
def yaw(q):return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
def odom(m):
 global pose,pose_received,fault
 p=m.pose.pose.position;cur=[p.x,p.y,yaw(m.pose.pose.orientation),m.header.stamp.sec+m.header.stamp.nanosec*1e-9]
 if m.header.frame_id!='camera_init':fault='Unexpected odometry frame';return
 if pose:
  dt=cur[3]-pose[3]
  if dt<=0:fault='Odometry timestamp did not advance'
  elif math.hypot(cur[0]-pose[0],cur[1]-pose[1])>.03+.5*dt or abs(angle(cur[2]-pose[2]))>.05+1.2*dt:fault='Pose jump outside bounded motion'
 pose=cur;pose_received=time.monotonic();history.append(cur);history[:]=history[-100:]
def costs(m):
 global grid,grid_received,fault,grid_metadata
 if m.header.frame_id!='camera_init':fault='Unexpected local costmap frame';return
 q=m.info.origin.orientation
 if abs(q.x)+abs(q.y)+abs(q.z)>1e-6:fault='Rotated costmap unsupported';return
 grid=(m.data,m.info.width,m.info.height,m.info.resolution,m.info.origin.position.x,m.info.origin.position.y);grid_received=time.monotonic()
 grid_metadata=dict(frame=m.header.frame_id,stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9)
def checked_sweep(v):
 global collision_snapshot
 try:swept_clear(grid,pose,v)
 except ValueError as e:
  # Capture in memory before ROS callbacks can replace it. Write only after stopping.
  collision_snapshot=dict(reason=str(e),captured=time.time(),pose=list(pose),command=list(v),
   grid=grid,metadata=dict(grid_metadata),grid_receipt_age_s=time.monotonic()-grid_received)
  raise
def cmd(m):
 global command
 command=([m.linear.x,m.linear.y,m.angular.z],time.monotonic())
n.create_subscription(Odometry,'/mppi/odom',odom,10);n.create_subscription(Twist,'/mppi/cmd_vel_smoothed',cmd,1);n.create_subscription(OccupancyGrid,'/local_costmap/costmap',costs,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
def healthy():
 if stop_requested or (route_action and (state/'route_cancel.request').exists()):raise RuntimeError('User interrupted')
 if fault:raise RuntimeError(fault)
 now=time.monotonic()
 if pose is None or grid is None or now-pose_received>.4 or now-grid_received>.8:
  result['stale_input_detail']=dict(odom_present=pose is not None,costmap_present=grid is not None,odom_receipt_age_s=now-pose_received,costmap_receipt_age_s=now-grid_received)
  raise RuntimeError('Odometry/costmap receipt stale: '+json.dumps(result['stale_input_detail']))
 for key in ('input','lifecycle','localization'):
  d=json.loads((state/(key+'.json')).read_text())
  if not d.get('ready') or time.time()-d['updated']>1:raise RuntimeError(key+' health lost')
  if key=='input':
   if d['session']!=target['source_session'] or max(d['pose_age_s'],d['cloud_age_s'])>.5:raise RuntimeError('Wrong session or sensor source lag')
  if key=='localization' and d['map_id']!=target['map_id']:raise RuntimeError('Map changed')
 runtime=json.loads((state/'runtime.json').read_text())
 if runtime['phase']!='running' or time.time()-runtime['updated']>1:raise RuntimeError('Navigation supervisor stopped')
def wait(f,timeout=10):
 end=time.monotonic()+timeout
 while not f.done() and time.monotonic()<end:
  if stop_requested:raise RuntimeError('User interrupted')
  rclpy.spin_once(n,timeout_sec=.02)
 if not f.done():raise RuntimeError('ROS action request timeout')
 return f.result()
def map_pose():
 t=buf.lookup_transform('map','go2w_mppi_base',rclpy.time.Time());p=t.transform.translation
 return [p.x,p.y,yaw(t.transform.rotation)]
def signal_stop(*_):
 global stop_requested
 stop_requested=True
signal.signal(signal.SIGINT,signal_stop);signal.signal(signal.SIGTERM,signal_stop)
try:
 end=time.monotonic()+4
 while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03)
 healthy();a=history[-1];recent=[p for p in history if a[3]-p[3]<2]
 if len(recent)<8 or max(math.hypot(p[0]-a[0],p[1]-a[1]) for p in recent)>.025 or max(abs(angle(p[2]-a[2])) for p in recent)>.025:raise RuntimeError('Start not stationary')
 checked_sweep((0.,0.,0.));result['start']=map_pose()
 p=PoseStamped();p.header.frame_id='map';p.pose.position.x,p.pose.position.y=target['pose'][:2];p.pose.orientation.z=math.sin(target['pose'][2]/2);p.pose.orientation.w=math.cos(target['pose'][2]/2)
 planner=ActionClient(n,ComputePathToPose,'/compute_path_to_pose')
 if not planner.wait_for_server(timeout_sec=3):raise RuntimeError('No planner server')
 g=ComputePathToPose.Goal();g.goal=p;g.planner_id='GridBased';pg=wait(planner.send_goal_async(g))
 if not pg.accepted:raise RuntimeError('Planner rejected target')
 planned=wait(pg.get_result_async());result['path_points']=len(planned.result.path.poses)
 if planned.status!=4 or not result['path_points']:raise RuntimeError('No valid path')
 path_xy=[(v.pose.position.x,v.pose.position.y) for v in planned.result.path.poses];result['planned_length_m']=sum(math.dist(a,b) for a,b in zip(path_xy,path_xy[1:]));result['recommended_timeout_s']=leg_timeout(result['planned_length_m'])
 healthy();nav=ActionClient(n,NavigateToPose,'/navigate_to_pose')
 if not nav.wait_for_server(timeout_sec=3):raise RuntimeError('No navigator')
 (state/'motion_active').write_text(json.dumps(dict(execute=execute,started=time.time())))
 guard=Guard(execute);guard.send((0.,0.,0.));g=NavigateToPose.Goal();g.pose=p;goal=wait(nav.send_goal_async(g))
 if not goal.accepted:raise RuntimeError('Navigate goal rejected')
 done=goal.get_result_async();start=time.monotonic();count=0
 with (state/('motion-commands-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl')).open('w') as log:
  while not done.done() and time.monotonic()-start<(timeout_s if execute else 8):
   tick=time.monotonic();rclpy.spin_once(n,timeout_sec=.01);healthy()
   if command is None:
    if tick-start>1:raise RuntimeError('Controller did not produce commands')
    guard.send((0.,0.,0.))
   else:
    v,created=command
    if time.monotonic()-created>.10:raise RuntimeError('Controller command stale')
    checked_sweep(v)
    age_before_send=time.monotonic()-created
    if age_before_send>.10:raise RuntimeError('Command exceeded 100 ms before transport')
    try:guard.send(v,created)
    except Exception as e:
     result['rejected_command']=dict(v=v,age_before_send_s=age_before_send)
     raise
    count+=1
    log.write(json.dumps(dict(t=time.time(),command=v,pose=pose,command_age_before_send_s=age_before_send,execute=execute))+'\n');log.flush()
   while time.monotonic()-tick<.05 and not done.done():rclpy.spin_once(n,timeout_sec=.005)
 if done.done():
  result['navigation_status']=done.result().status
  if done.result().status!=4:result['reason']='Nav2 action ended with status '+str(done.result().status)+'; inspect controller/planner logs'
 else:result['reason']='Execution deadline' if execute else 'Preview duration reached'
 result['commands']=count;result['timeout_s']=timeout_s
except Exception as e:
 result['reason']=str(e)
 if getattr(e,'stop',None):result['guard_stop']=e.stop
finally:
 # Stop transport first: a delayed ROS cancellation cannot keep the robot moving.
 if guard:
  try:result['guard_stop']=guard.close()
  except Exception as e:result['guard_stop_error']=str(e)
 if goal:
  try:
   stop_requested=False;wait(goal.cancel_goal_async(),3)
  except Exception as e:result['cancel_error']=str(e)
 end=time.monotonic()+2
 while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.02)
 try:
  healthy();last=map_pose();result['last_pose']=last;result['estimated_xy_error']=math.hypot(last[0]-target['pose'][0],last[1]-target['pose'][1]);result['estimated_yaw_error']=abs(angle(last[2]-target['pose'][2]));result['stationary_after_stop']=stationary(history);result['success']=execute and result['stationary_after_stop'] and result.get('navigation_status')==4 and result['estimated_xy_error']<=.08 and result['estimated_yaw_error']<=.12 and result.get('guard_stop',{}).get('stop_code')==0
 except Exception as e:result['final_health_error']=str(e)
 result['preview_passed']=not execute and not result.get('final_health_error') and result.get('guard_stop',{}).get('stop_code')==0 and (result.get('navigation_status')==4 or result.get('reason')=='Preview duration reached')
 if collision_snapshot is not None:
  try:
   snapshot=dict(collision_snapshot);data,width,height,res,ox,oy=snapshot.pop('grid')
   snapshot['costmap']=dict(width=width,height=height,resolution=res,origin=[ox,oy],data=list(data))
   evidence_path=state/('failure-local-sweep-'+str(time.time_ns())+'.json')
   evidence_path.write_text(json.dumps(snapshot));result['local_collision_evidence']=str(evidence_path)
  except Exception as e:result['local_collision_evidence_error']=str(e)
 (state/'motion_active').unlink(missing_ok=True)
 if execute and not result['success']:
  grids_path=state/('failure-global-costmaps-'+time.strftime('%Y%m%d-%H%M%S')+'.json');grids_path.write_text(json.dumps(global_grids));result['global_costmap_evidence']=str(grids_path)
 path=state/('protected-'+('execute' if execute else 'preview')+'-'+time.strftime('%Y%m%d-%H%M%S')+'.json');path.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));n.destroy_node();rclpy.try_shutdown()

raise SystemExit(0 if result['success'] or result['preview_passed'] else 1)
