"""Capture TF-aligned full-direction navigation scans without changing their stamps."""
import time,json
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
from tf2_ros import Buffer,TransformListener
from scipy.spatial.transform import Rotation
rclpy.init();n=Node('relocal_capture');b=Buffer();l=TransformListener(b,n);pending=[];chunks=[];poses=[]
def cb(m):pending.append(m)
n.create_subscription(PointCloud2,'/mppi/cloud',cb,10);end=time.monotonic()+8
while time.monotonic()<end:
 rclpy.spin_once(n,timeout_sec=.02)
 for m in pending[:]:
  try:t=b.lookup_transform('camera_init',m.header.frame_id,Time.from_msg(m.header.stamp))
  except Exception:continue
  q=t.transform.rotation;p=t.transform.translation;R=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix();a=np.frombuffer(m.data,dtype='<f4').reshape(-1,3);chunks.append(a@R.T+np.array([p.x,p.y,p.z]));pending.remove(m)
 pending=pending[-4:]
if len(chunks)<20:raise RuntimeError('Not enough aligned scans')
a=np.concatenate(chunks);_,i=np.unique(np.floor(a/.08).astype(np.int32),axis=0,return_index=True);a=a[i];root=Path('/state');np.save(root/'local_scan.npy',a);(root/'local_scan.json').write_text(json.dumps(dict(points=len(a),frames=len(chunks),captured=time.time(),frame='camera_init')));print('captured',len(a),len(chunks));n.destroy_node();rclpy.shutdown()
