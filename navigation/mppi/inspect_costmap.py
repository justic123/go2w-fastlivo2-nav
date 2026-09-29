"""Read-only snapshot for path failure diagnosis."""
import json,time,math
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid
from tf2_ros import Buffer,TransformListener
rclpy.init();n=Node('inspect_path_failure');b=Buffer();li=TransformListener(b,n);maps={};q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
for k,t in [('global','/global_costmap/costmap'),('local','/local_costmap/costmap'),('saved','/map')]:n.create_subscription(OccupancyGrid,t,lambda m,k=k:maps.__setitem__(k,m),q)
end=time.monotonic()+4
while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
target=json.loads(Path('/state/accuracy_target.json').read_text())['pose'];result={}
for k,m in maps.items():
 tf=b.lookup_transform(m.header.frame_id,'go2w_mppi_base',rclpy.time.Time());p=tf.transform.translation;points={'robot':(p.x,p.y)}
 if m.header.frame_id=='map':points['goal']=target[:2]
 d=dict(frame=m.header.frame_id,resolution=m.info.resolution,points={})
 for name,(x,y) in points.items():
  ix=math.floor((x-m.info.origin.position.x)/m.info.resolution);iy=math.floor((y-m.info.origin.position.y)/m.info.resolution);cells=[]
  for dy in range(-2,3):
   row=[]
   for dx in range(-2,3):
    a,c=ix+dx,iy+dy;row.append(int(m.data[c*m.info.width+a]) if 0<=a<m.info.width and 0<=c<m.info.height else None)
   cells.append(row)
  d['points'][name]=dict(x=x,y=y,cell=[ix,iy],neighborhood=cells)
 result[k]=d
Path('/state/path_failure_costs.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));n.destroy_node();rclpy.shutdown()
