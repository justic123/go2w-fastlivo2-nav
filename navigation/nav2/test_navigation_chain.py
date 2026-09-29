#!/usr/bin/env python3
"""Isolated domain 79 integration of real planner/controller/runner/watchdog.
Only --preview-nav runs; fixture NEVER integrates commands into robot motion.
"""
import os,json,subprocess,tempfile,time,shutil
from pathlib import Path
import yaml,rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import Odometry,OccupancyGrid
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
assert os.environ.get('ROS_DOMAIN_ID')=='79'
source=Path(__file__).parent;production=source.parent.parent
work=Path(tempfile.mkdtemp(prefix='go2w-nav-chain-'));shm=work/'shm';shm.mkdir();(work/'navigation/build').mkdir(parents=True)
shutil.copy2(production/'navigation/build/sport_guard',work/'navigation/build/sport_guard')
shutil.copy2(source/'motion_policy.py',work/'motion_policy.py')
shutil.copy2(source/'mapping_session.py',work/'mapping_session.py')
script=(source/'navigate.py').read_text().replace("Path('/home/unitree/fast_livo2_port/build1')",'Path('+repr(str(work))+')').replace("Path('/dev/shm/go2w_nav')",'Path('+repr(str(shm))+')')
(work/'navigate.py').write_text(script);(work/'continuous_capture.json').write_text(json.dumps(dict(run='synthetic')))
cfg=yaml.safe_load((source/'preview.yaml').read_text())
for name in ['global_costmap','local_costmap']:
 c=cfg[name][name]['ros__parameters'];c['rolling_window']=False;c['plugins']=['static_layer','inflation_layer'];c.pop('obstacle_layer');c['static_layer']={'plugin':'nav2_costmap_2d::StaticLayer','map_topic':'/fixture_map','map_subscribe_transient_local':True};c['publish_frequency']=5.0
(work/'params.yaml').write_text(yaml.safe_dump(cfg))
rclpy.init();node=Node('nav_chain_fixture');tf=TransformBroadcaster(node);q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL);mp=node.create_publisher(OccupancyGrid,'/fixture_map',q);op=node.create_publisher(Odometry,'/go2w_nav/odom',10)
m=OccupancyGrid();m.header.frame_id='camera_init';m.info.resolution=.1;m.info.width=100;m.info.height=100;m.info.origin.position.x=-5.;m.info.origin.position.y=-5.;m.info.origin.orientation.w=1.;m.data=[0]*10000
last=0
fault_mode=None
def atomic(name,d):
 p=shm/name;tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d));tmp.replace(p)
def tick():
 global last
 now=node.get_clock().now().to_msg();wall=time.time()
 t=TransformStamped();t.header.frame_id='camera_init';t.child_frame_id='go2w_base';t.header.stamp=now;t.transform.rotation.w=1.;tf.sendTransform(t)
 o=Odometry();o.header=t.header;o.child_frame_id=t.child_frame_id;o.pose.pose.orientation.w=1.;op.publish(o)
 if time.monotonic()-last>.5:m.header.stamp=now;mp.publish(m);last=time.monotonic()
 atomic('adapter_status.json',dict(last_check=wall,pose_age_s=.01,cloud_age_s=2. if fault_mode=='stale' else .02))
 atomic('imu_health.json',dict(stamp=wall,receipt=wall,fault=None))
node.create_timer(.05,tick)
def spin(sec):
 end=time.monotonic()+sec
 while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.02)
children=[];files=[];goal=None;results=[]
try:
 for pkg,binary,extra in [('nav2_planner','planner_server',['-r','__node:=planner_server']),('nav2_controller','controller_server',['-r','cmd_vel:=/go2w_nav/proposed_cmd_vel']),('nav2_lifecycle_manager','lifecycle_manager',[])]:
  f=(work/(binary+'.log')).open('w');files.append(f);children.append(subprocess.Popen(['/opt/ros/foxy/lib/'+pkg+'/'+binary,'--ros-args','--params-file',str(work/'params.yaml')]+extra,stdout=f,stderr=f))
 spin(6)
 for case in ['normal','lease_lost','lease_silent','stale']:
  fault_mode=None;out=work/case;f=(work/(case+'.log')).open('w');files.append(f)
  goal=subprocess.Popen(['python3',str(work/'navigate.py'),'--forward','.5','--output',str(out)],stdin=subprocess.PIPE,stdout=f,stderr=f,text=True)
  started=time.monotonic();lastbeat=0;injected=False
  while goal.poll() is None and time.monotonic()-started<22:
   rclpy.spin_once(node,timeout_sec=.02)
   if (out/'guard.log').exists() and not injected and case!='normal':
    injected=True
    if case=='lease_lost':goal.stdin.close()
    elif case=='stale':fault_mode='stale'
   if not (injected and case in ('lease_lost','lease_silent')) and time.monotonic()-lastbeat>.15:
    try:goal.stdin.write('HEARTBEAT\n');goal.stdin.flush()
    except BrokenPipeError:pass
    lastbeat=time.monotonic()
  if goal.poll() is None:goal.terminate();goal.wait(timeout=4)
  rr=json.loads((out/'result.json').read_text());guard=(out/'guard.log').read_text() if (out/'guard.log').exists() else ''
  assert not rr['execute'] and '"execute":true' not in guard
  if case=='normal':assert rr['success'],rr
  else:assert injected and not rr['success'] and ('disconnected' in rr['reason'] if case=='lease_lost' else 'heartbeat expired' in rr['reason'] if case=='lease_silent' else 'cloud_age_s stale' in rr['reason']),rr
  assert '"stopped":true' in guard
  results.append(dict(case=case,passed=True,result=rr,guard=guard));goal=None;spin(2)
 output=production/'nav2-chain-tests.json';output.write_text(json.dumps(results,indent=2));print(json.dumps(dict(work=str(work),cases=[dict(case=r['case'],passed=True) for r in results])))
finally:
 if goal and goal.poll() is None:goal.terminate();goal.wait(timeout=4)
 for p in children:p.terminate()
 for p in children:
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for f in files:f.close()
 node.destroy_node();rclpy.shutdown()
 print('Fixture logs: '+str(work))
