"""Read-only live planning/controller probes; sim-goal moves ONLY the synthetic robot."""
import sys,time,json,math,os
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import ComputePathToPose,NavigateToPose
from geometry_msgs.msg import PoseStamped,Twist
from nav_msgs.msg import Odometry
import numpy as np
from scipy.spatial.transform import Rotation
rclpy.init();node=Node('mppi_probe');root=Path('/state');action=sys.argv[1];mode=os.environ.get('MPPI_MODE')
commands=[];pose=None

def cmd(m):commands.append(dict(t=time.monotonic(),vx=m.linear.x,vy=m.linear.y,w=m.angular.z))
def odom(m):
 global pose
 p=m.pose.pose.position;q=m.pose.pose.orientation
 if Path('/work/selection.json').exists():
  loc=json.loads((root/'localization.json').read_text());T=np.array(loc['transform']);xyz=T[:3,:3]@np.array([p.x,p.y,p.z])+T[:3,3];R=T[:3,:3]@Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix();pose=[float(xyz[0]),float(xyz[1]),math.atan2(R[1,0],R[0,0])];return
 pose=[p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))]
node.create_subscription(Twist,'/mppi/cmd_vel_smoothed',cmd,100)
node.create_subscription(Odometry,'/mppi/odom',odom,10)
def wait(f,seconds=10):
 deadline=time.monotonic()+seconds
 while not f.done() and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
 if not f.done():raise RuntimeError('ROS request timeout')
 return f.result()
def spin(seconds):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
result=dict(action=action,mode=mode,actuation_enabled=False);goal=None
try:
 states={};clients={};deadline=time.monotonic()+20
 for name in ((['map_server'] if Path('/work/selection.json').exists() else [])+['planner_server','controller_server','velocity_smoother','bt_navigator']):
  clients[name]=node.create_client(GetState,'/'+name+'/get_state')
  if not clients[name].wait_for_service(timeout_sec=8):raise RuntimeError(name+' service unavailable')
 while time.monotonic()<deadline:
  for name,c in clients.items():states[name]=wait(c.call_async(GetState.Request())).current_state.label
  if all(s=='active' for s in states.values()):break
  spin(.2)
 result['lifecycle']=states
 if any(s!='active' for s in states.values()):raise RuntimeError('Nav2 nodes not all active')
 d=json.loads((root/'input.json').read_text())
 if not d['ready'] or time.time()-d['updated']>1:raise RuntimeError('No fresh input')
 result['input']=d
 if Path('/work/selection.json').exists():
  loc=json.loads((root/'localization.json').read_text())
  if not loc['ready'] or time.time()-loc['updated']>1:raise RuntimeError('Saved-map localization not fresh')
  result['localization']=loc
 if action=='check':result['success']=True
 else:
  if len(sys.argv)!=5:raise ValueError('Provide x y yaw in camera_init coordinates')
  target=list(map(float,sys.argv[2:5]))
  if not all(math.isfinite(v) for v in target):raise ValueError('Nonfinite goal')
  p=PoseStamped();p.header.frame_id='map' if Path('/work/selection.json').exists() else 'camera_init';p.pose.position.x,p.pose.position.y=target[:2];p.pose.orientation.z=math.sin(target[2]/2);p.pose.orientation.w=math.cos(target[2]/2)
  planner=ActionClient(node,ComputePathToPose,'/compute_path_to_pose');planner.wait_for_server(timeout_sec=5)
  g=ComputePathToPose.Goal();g.goal=p;g.planner_id='GridBased';g.use_start=False
  goal=wait(planner.send_goal_async(g))
  if not goal.accepted:raise RuntimeError('Planner rejected goal')
  planned=wait(goal.get_result_async(),15);goal=None
  result.update(target=target,planner_status=planned.status,path_points=len(planned.result.path.poses))
  if planned.status!=4 or not planned.result.path.poses:raise RuntimeError('No valid global path')
  if action=='preview':result['success']=True
  elif action in ('shadow','sim-goal'):
   if action=='sim-goal' and mode!='simulation':raise RuntimeError('sim-goal is restricted to the synthetic robot')
   nav=ActionClient(node,NavigateToPose,'/navigate_to_pose');nav.wait_for_server(timeout_sec=5);g=NavigateToPose.Goal();g.pose=p
   goal=wait(nav.send_goal_async(g))
   if not goal.accepted:raise RuntimeError('Navigator rejected goal')
   done=goal.get_result_async();deadline=time.monotonic()+(90 if action=='sim-goal' else 8)
   while not done.done() and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.03)
   if not done.done():wait(goal.cancel_goal_async());wait(done,5)
   result.update(navigation_status=done.result().status,commands=len(commands),last_pose=pose)
   if commands:
    result.update(max_vx=max(c['vx'] for c in commands),min_vx=min(c['vx'] for c in commands),max_abs_vy=max(abs(c['vy']) for c in commands),max_abs_w=max(abs(c['w']) for c in commands))
    gaps=[commands[i]['t']-commands[i-1]['t'] for i in range(1,len(commands))];result['command_hz']=(len(commands)-1)/(commands[-1]['t']-commands[0]['t']) if gaps else None
   result['success']=done.result().status==4 if action=='sim-goal' else bool(commands) and done.result().status in (4,5)
   if pose:
    result['estimated_xy_error']=math.hypot(pose[0]-target[0],pose[1]-target[1]);result['estimated_yaw_error']=abs(math.atan2(math.sin(pose[2]-target[2]),math.cos(pose[2]-target[2])))
   if action=='sim-goal':result['success']=result['success'] and result.get('estimated_xy_error',999)<=.08 and result.get('estimated_yaw_error',999)<=.12
  else:raise ValueError('Unsupported probe')
except Exception as e:result.update(success=False,error=str(e))
finally:
 if goal:
  try:wait(goal.cancel_goal_async(),3)
  except Exception:pass
 spin(1.2);result['after_stop_command']=commands[-1] if commands else None
 if action in ('shadow','sim-goal') and commands and any(abs(commands[-1][k])>1e-5 for k in ('vx','vy','w')):result.update(success=False,error='Candidate command failed to settle to zero after cancel')
 path=root/(action+'-'+time.strftime('%Y%m%d-%H%M%S')+'.json');path.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));node.destroy_node();rclpy.shutdown()
raise SystemExit(0 if result.get('success') else 1)
