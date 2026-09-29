#!/usr/bin/env python3
"""Request a path and optionally sample isolated DWB velocities. NEVER executes robot motion."""
import argparse,json,math,time,fcntl
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose,FollowPath
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
p=argparse.ArgumentParser();p.add_argument('--forward',type=float,default=.8);p.add_argument('--left',type=float,default=0.);p.add_argument('--sample-controller',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
if not all(math.isfinite(x) for x in [a.forward,a.left]) or math.hypot(a.forward,a.left)>5:raise SystemExit('preview goal must be within 5m')
trial_lock=open('/home/unitree/fast_livo2_port/build1/point_trial.lock','w')
try:fcntl.flock(trial_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Another motion/plan trial is running')
rclpy.init();node=Node('go2w_plan_probe');pose=[];cmd=[]
node.create_subscription(Odometry,'/go2w_nav/odom',lambda m:pose.append(m),1)
node.create_subscription(Twist,'/go2w_nav/proposed_cmd_vel',lambda m:cmd.append(dict(vx=m.linear.x,vy=m.linear.y,w=m.angular.z)),10)
def wait(f,seconds=15):
 end=time.monotonic()+seconds
 while not f.done() and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
 if not f.done():raise TimeoutError('Nav2 action timeout')
 return f.result()
c=None;follow=None
r=dict(actuation_enabled=False,requested_forward_m=a.forward,requested_left_m=a.left)
try:
 deadline=time.monotonic()+3
 while True:
  
  try:health=json.loads(Path('/dev/shm/go2w_nav/adapter_status.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):health={'last_check':0}
  if 0<=time.time()-health['last_check']<1 and health.get('pose_age_s') is not None and health.get('cloud_age_s') is not None and 0<=health['pose_age_s']<.85 and 0<=health['cloud_age_s']<.8:break
  if time.monotonic()>deadline:raise RuntimeError('Navigation input stale; refuse new plan')
  time.sleep(.05)
 end=time.monotonic()+10
 while not pose and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
 if not pose:raise RuntimeError('No navigation odometry')
 m=pose[-1];stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9
 if not 0<=time.time()-stamp<1:raise RuntimeError('Stale navigation odometry')
 q=m.pose.pose.orientation;yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
 goal=ComputePathToPose.Goal();goal.planner_id='GridBased';goal.pose.header.frame_id='camera_init';goal.pose.header.stamp=node.get_clock().now().to_msg();goal.pose.pose.position.x=m.pose.pose.position.x+math.cos(yaw)*a.forward-math.sin(yaw)*a.left;goal.pose.pose.position.y=m.pose.pose.position.y+math.sin(yaw)*a.forward+math.cos(yaw)*a.left;goal.pose.pose.orientation=q
 c=ActionClient(node,ComputePathToPose,'compute_path_to_pose')
 if not c.wait_for_server(timeout_sec=10):raise RuntimeError('Planner unavailable')
 g=wait(c.send_goal_async(goal))
 if not g.accepted:raise RuntimeError('Goal rejected')
 result=wait(g.get_result_async());r['planner_status']=result.status;r['path']=[[p.pose.position.x,p.pose.position.y] for p in result.result.path.poses]
 if result.status!=4 or not r['path']:raise RuntimeError('Planner did not find a valid path')
 if a.sample_controller:
  follow=ActionClient(node,FollowPath,'follow_path')
  if not follow.wait_for_server(timeout_sec=5):raise RuntimeError('Controller unavailable')
  fg=FollowPath.Goal();fg.path=result.result.path;fg.controller_id='FollowPath';h=wait(follow.send_goal_async(fg))
  if not h.accepted:raise RuntimeError('Controller rejected path')
  end=time.monotonic()+3
  while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
  wait(h.cancel_goal_async());r['controller_result_status']=wait(h.get_result_async()).status
 r['commands']=cmd;r['ok']=True
except Exception as e:r['error']=str(e);r['ok']=False
finally:
 Path(a.output).write_text(json.dumps(r,indent=2));print(json.dumps(r));
 if follow is not None:follow.destroy();follow=None
 if c is not None:c.destroy();c=None
 node.destroy_node();rclpy.shutdown()
raise SystemExit(0 if r['ok'] else 1)
