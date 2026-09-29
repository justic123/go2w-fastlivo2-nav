#!/usr/bin/env python3
"""Export a 10cm voxel XYZ map and full odometry from isolated diagnostic bag."""
import sys,json,math
from pathlib import Path
import numpy as np,rosbag
root=Path(sys.argv[1]);cloud_topic='/go2w_lio/cloud';odom_topic='/go2w_lio/odometry'
voxels={};trajectory=[];counts={};rejected=0;cloud_frame=None
with rosbag.Bag(str(root/'sensors.bag')) as bag:
 for topic,msg,t in bag.read_messages(topics=[cloud_topic,odom_topic]):
  counts[topic]=counts.get(topic,0)+1
  if topic==odom_topic:
   p=msg.pose.pose.position;q=msg.pose.pose.orientation
   values=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]
   if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite pose')
   trajectory.append([msg.header.stamp.to_sec()]+values)
  elif topic==cloud_topic:
   if msg.width*msg.height==0:continue
   if cloud_frame is not None and cloud_frame!=msg.header.frame_id:raise ValueError('Cloud frame changed')
   cloud_frame=msg.header.frame_id
   fs={f.name:f for f in msg.fields};endian='>' if msg.is_bigendian else '<'
   if any(fs[k].datatype!=7 for k in ['x','y','z']):raise ValueError('Expected float32 XYZ')
   dt=np.dtype({'names':['x','y','z'],'formats':[endian+'f4']*3,'offsets':[fs[k].offset for k in ['x','y','z']],'itemsize':msg.point_step})
   a=np.ndarray(shape=(msg.height,msg.width),dtype=dt,buffer=msg.data,strides=(msg.row_step,msg.point_step))
   xyz=np.stack([a[k].ravel() for k in ['x','y','z']],axis=1);valid=np.isfinite(xyz).all(axis=1);rejected+=int((~valid).sum());xyz=xyz[valid]
   keys=np.floor(xyz/.1).astype(np.int64);_,inds=np.unique(keys,axis=0,return_index=True)
   for i in inds:voxels[tuple(keys[i])]=xyz[i]
   if len(voxels)>3000000:raise ValueError('Map exceeds 3 million voxel guard')
xyz=np.asarray(list(voxels.values()),dtype='<f4').reshape(-1,3)
header=f'# .PCD v0.7\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH {len(xyz)}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {len(xyz)}\nDATA binary\n'
with (root/'map_xyz_10cm.pcd').open('wb') as f:f.write(header.encode());f.write(xyz.tobytes())
np.savetxt(root/'trajectory.tum',np.asarray(trajectory).reshape(-1,8),fmt='%.9f')
pos=np.asarray([r[1:4] for r in trajectory]);stats=dict(topic_counts=counts,voxel_m=.1,map_points=len(xyz),map_frame=cloud_frame,nonfinite_cloud_points=rejected,poses=len(pos),estimated_path_length_m=float(np.linalg.norm(np.diff(pos,axis=0),axis=1).sum()) if len(pos)>1 else 0,estimated_endpoint_displacement_m=float(np.linalg.norm(pos[-1]-pos[0])) if len(pos)>1 else 0,ground_truth_available=False)
if len(xyz):stats['map_bounds_m']=[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()]
(root/'mapping_result.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2))
if not len(xyz) or len(pos)<10:raise SystemExit(1)
