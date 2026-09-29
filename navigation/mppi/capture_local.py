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
root=Path('/state');initial=json.loads((root/'input.json').read_text());session=initial['session']
if not initial.get('ready') or not 0<=time.time()-initial['updated']<1:raise RuntimeError('No fresh localization input')
rclpy.init();n=Node('relocal_capture');b=Buffer();l=TransformListener(b,n);pending=[];chunks=[];poses=[]
def cb(m):pending.append(m)
n.create_subscription(PointCloud2,'/mppi/cloud',cb,10);end=time.monotonic()+8
while time.monotonic()<end:
 rclpy.spin_once(n,timeout_sec=.02)
 for m in pending[:]:
  try:t=b.lookup_transform('camera_init',m.header.frame_id,Time.from_msg(m.header.stamp))
  except Exception:continue
  q=t.transform.rotation;p=t.transform.translation;R=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix();xyz=np.array([p.x,p.y,p.z]);poses.append((xyz,R));a=np.frombuffer(m.data,dtype='<f4').reshape(-1,3);chunks.append(a@R.T+xyz);pending.remove(m)
 pending=pending[-4:]
if len(chunks)<20:raise RuntimeError('Not enough aligned scans')
if any(np.linalg.norm(p-poses[0][0])>.03 or np.linalg.norm(Rotation.from_matrix(poses[0][1].T@R).as_rotvec())>.04 for p,R in poses):raise RuntimeError('Robot moved during capture; keep stationary and retry')
final=json.loads((root/'input.json').read_text())
if final['session']!=session or not final.get('ready') or not 0<=time.time()-final['updated']<1:raise RuntimeError('Input lost or session changed during capture')
a=np.concatenate(chunks);_,i=np.unique(np.floor(a/.08).astype(np.int32),axis=0,return_index=True);a=a[i];np.save(root/'local_scan.npy',a);(root/'local_scan.json').write_text(json.dumps(dict(points=len(a),frames=len(chunks),captured=time.time(),frame='camera_init',session=session)));print('captured',len(a),len(chunks));n.destroy_node();rclpy.shutdown()
