"""Plan every mission segment using explicit start poses. Never sends a nav action or SDK call."""
import json,time,math
from pathlib import Path
import rclpy
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose
from tf2_ros import Buffer,TransformListener
from route_model import leg_timeout
root=Path('/state');spec=json.loads((root/'route_request.json').read_text());result=dict(success=False,execute=False,fingerprint=spec['fingerprint'],map_id=spec['map_id'],source_session=spec['source_session'],segments=[])
rclpy.init();n=rclpy.create_node('mission_plan',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)]);buf=Buffer();listener=TransformListener(buf,n);active=None

def health():
 for name in ('input','localization','lifecycle'):
  d=json.loads((root/(name+'.json')).read_text())
  if not d.get('ready') or not 0<=time.time()-d['updated']<1:raise RuntimeError(name+' not fresh')
  if name=='input' and d['session']!=spec['source_session']:raise RuntimeError('Session changed')
  if name=='localization' and d['map_id']!=spec['map_id']:raise RuntimeError('Map changed')

def wait(f):
 end=time.monotonic()+15
 while not f.done() and time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03);health()
 if not f.done():raise RuntimeError('Planning timeout')
 return f.result()
def pose(v):
 m=PoseStamped();m.header.frame_id='map';m.pose.position.x,m.pose.position.y=map(float,v[:2]);m.pose.orientation.z=math.sin(v[2]/2);m.pose.orientation.w=math.cos(v[2]/2);return m
try:
 end=time.monotonic()+2
 while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.02)
 health();t=buf.lookup_transform('map','go2w_mppi_base',rclpy.time.Time());p=t.transform.translation;q=t.transform.rotation
 start=[p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))];result['start']=start;prior=pose(start)
 client=ActionClient(n,ComputePathToPose,'/compute_path_to_pose')
 if not client.wait_for_server(timeout_sec=3):raise RuntimeError('Planner unavailable')
 for index,target in enumerate(spec['targets']):
  g=ComputePathToPose.Goal();g.goal=pose(target['pose']);g.start=prior;g.use_start=True;g.planner_id='GridBased';active=wait(client.send_goal_async(g))
  if not active.accepted:raise RuntimeError('Planner rejected segment')
  r=wait(active.get_result_async());active=None
  if r.status!=4 or not r.result.path.poses:raise RuntimeError('No valid path to '+target['name'])
  points=[[p.pose.position.x,p.pose.position.y] for p in r.result.path.poses];length=sum(math.dist(a,b) for a,b in zip(points,points[1:]));budget=leg_timeout(length)
  result['segments'].append(dict(index=index,name=target['name'],path=points,length_m=length,timeout_s=budget));prior=g.goal
  print(json.dumps(dict(segment=index+1,name=target['name'],length_m=round(length,2),timeout_s=budget),ensure_ascii=False),flush=True)
 health();result['success']=True
except Exception as e:result['reason']=str(e)
finally:
 if active:
  try:wait(active.cancel_goal_async())
  except Exception:pass
 result['created']=time.time();tmp=root/'route_preview.tmp';tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(root/'route_preview.json');n.destroy_node();rclpy.try_shutdown()
print(json.dumps({k:v for k,v in result.items() if k!='segments'},ensure_ascii=False),flush=True)
raise SystemExit(0 if result['success'] else 1)
