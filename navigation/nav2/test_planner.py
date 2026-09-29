#!/usr/bin/env python3
"""Isolated ROS_DOMAIN_ID=79 synthetic A* obstacle / no-path tests. No robot SDK."""
import os,json,subprocess,tempfile,time,math
from pathlib import Path
import yaml,rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
assert os.environ.get('ROS_DOMAIN_ID')=='79'
rclpy.init();node=Node('synthetic_nav_test');tf=TransformBroadcaster(node);q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL);pub=node.create_publisher(OccupancyGrid,'/fixture_map',q)
m=OccupancyGrid();m.header.frame_id='camera_init';m.info.resolution=.1;m.info.width=100;m.info.height=100;m.info.origin.position.x=-5.;m.info.origin.position.y=-5.;m.info.origin.orientation.w=1.;m.data=[0]*10000
phase=['open'];lastpub=[0.]
def tick():
 now=node.get_clock().now().to_msg();t=TransformStamped();t.header.frame_id='camera_init';t.child_frame_id='go2w_base';t.header.stamp=now;t.transform.rotation.w=1.;tf.sendTransform(t)
 if time.monotonic()-lastpub[0]>1:m.header.stamp=now;pub.publish(m);lastpub[0]=time.monotonic()
node.create_timer(.05,tick)
def spin(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.05)
def wait(f,timeout=15):
 end=time.monotonic()+timeout
 while not f.done() and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.05)
 if not f.done():raise TimeoutError()
 return f.result()
cfg={'planner_server':{'ros__parameters':{'planner_plugins':['GridBased'],'GridBased':{'plugin':'nav2_navfn_planner/NavfnPlanner','use_astar':True,'allow_unknown':False,'tolerance':.1}}},'global_costmap':{'global_costmap':{'ros__parameters':{'global_frame':'camera_init','robot_base_frame':'go2w_base','robot_radius':.55,'resolution':.1,'update_frequency':5.0,'publish_frequency':2.0,'track_unknown_space':True,'plugins':['static_layer','inflation_layer'],'static_layer':{'plugin':'nav2_costmap_2d::StaticLayer','map_topic':'/fixture_map','map_subscribe_transient_local':True},'inflation_layer':{'plugin':'nav2_costmap_2d::InflationLayer','inflation_radius':.8,'cost_scaling_factor':3.0}}}},'lifecycle_manager':{'ros__parameters':{'autostart':True,'node_names':['planner_server']}}}
output=Path('/home/unitree/fast_livo2_port/build1/nav2-synthetic-tests');output.mkdir(exist_ok=True);config=output/'params.yaml';config.write_text(yaml.safe_dump(cfg));children=[];handles=[];results=[];client=None
try:
 for pkg,binary,extra in [('nav2_planner','planner_server',['-r','__node:=planner_server']),('nav2_lifecycle_manager','lifecycle_manager',[])]:
  f=(output/(binary+'.log')).open('w');handles.append(f);children.append(subprocess.Popen(['/opt/ros/foxy/lib/'+pkg+'/'+binary,'--ros-args','--params-file',str(config)]+extra,stdout=f,stderr=f))
 client=ActionClient(node,ComputePathToPose,'compute_path_to_pose');spin(5)
 if not client.wait_for_server(timeout_sec=5):raise RuntimeError('planner not available')
 for label in ['open','obstacle','blocked']:
  data=[0]*10000
  if label!='open':
   for iy in range(100):
    y=-5+(iy+.5)*.1
    if label=='blocked' or abs(y)<.4:
     for ix in range(60,63):data[iy*100+ix]=100
  m.data=data;pub.publish(m);spin(3)
  g=ComputePathToPose.Goal();g.pose.header.frame_id='camera_init';g.pose.header.stamp=node.get_clock().now().to_msg();g.pose.pose.position.x=3.;g.pose.pose.orientation.w=1.;g.planner_id='GridBased';h=wait(client.send_goal_async(g));result=wait(h.get_result_async());path=[[p.pose.position.x,p.pose.position.y] for p in result.result.path.poses];r=dict(case=label,status=result.status,path=path,actuation_enabled=False)
  if label=='blocked':assert result.status!=4
  else:
   assert result.status==4 and len(path)>5
   if label=='obstacle':assert max(abs(p[1]) for p in path)>.85,'did not detour around inflated obstacle'
  r['pass']=True;results.append(r)
 (output/'result.json').write_text(json.dumps(results,indent=2));print(json.dumps([dict(case=r['case'],status=r['status'],points=len(r['path']),passed=r['pass']) for r in results]))
finally:
 for p in children:p.terminate()
 for p in children:
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for f in handles:f.close()
 # Foxy ActionClient destructor must run while its Node handle is still valid.
 if client is not None:client.destroy();client=None
 node.destroy_node();rclpy.shutdown()
