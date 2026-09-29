"""Accumulate full-direction TF-aligned navigation scans, without actuation."""
import json,time
from pathlib import Path
import numpy as np,rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
from tf2_ros import Buffer,TransformListener
from scipy.spatial.transform import Rotation
root=Path('/state/demo-map');root.mkdir(exist_ok=True)
points=np.empty((0,3),dtype=np.float32);frames=0;pending=[]
def report(phase,**kw):
 t=root/'status.tmp';t.write_text(json.dumps(dict(phase=phase,points=len(points),frames=frames,updated=time.time(),**kw)));t.replace(root/'status.json')
def callback(m):
 if m.width*m.height and m.data:pending.append(m)
rclpy.init();node=Node('demo_map_collector',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)]);buf=Buffer();listener=TransformListener(buf,node)
node.create_subscription(PointCloud2,'/mppi/cloud',callback,5);last_stamp=-1e30;received=time.monotonic()
try:
 report('collecting')
 while rclpy.ok() and not (root/'finish.request').exists():
  rclpy.spin_once(node,timeout_sec=.05)
  for m in pending[:]:
   stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9
   if stamp-last_stamp<.5:pending.remove(m);continue
   try:tf=buf.lookup_transform('camera_init',m.header.frame_id,Time.from_msg(m.header.stamp))
   except Exception:continue
   q=tf.transform.rotation;p=tf.transform.translation;R=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix()
   a=np.frombuffer(m.data,dtype='<f4').reshape(-1,3);a=a@R.T+np.array([p.x,p.y,p.z]);a=a[np.isfinite(a).all(1)]
   points=np.concatenate([points,a]).astype(np.float32);_,idx=np.unique(np.floor(points/.08).astype(np.int64),axis=0,return_index=True);points=points[idx]
   if len(points)>2000000:raise RuntimeError('More than 2 million voxels; use a smaller demo scene')
   frames+=1;last_stamp=stamp;received=time.monotonic();pending.remove(m)
  pending=pending[-5:]
  if time.monotonic()-received>5:raise RuntimeError('No fresh TF-aligned lidar scans')
  report('collecting')
 if not rclpy.ok():raise RuntimeError('Interrupted before saving')
 if frames<10 or len(points)<1000:raise RuntimeError('Insufficient full-direction observations')
 with (root/'points.tmp').open('wb') as f:np.save(f,points)
 (root/'points.tmp').replace(root/'points.npy');report('saved',frame='camera_init',voxel=.08)
except Exception as e:report('failed',error=str(e));raise
finally:node.destroy_node();rclpy.try_shutdown()
