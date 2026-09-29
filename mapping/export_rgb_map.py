#!/usr/bin/env python3
"""Export colored registered points; voxel spacing is not an accuracy claim."""
import argparse,json
from pathlib import Path
import numpy as np,rosbag
p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--voxel',type=float,default=.02);a=p.parse_args();assert .005<=a.voxel<=.2
root=Path(a.run);voxels={};frames=0;input_points=0
with rosbag.Bag(str(root/'sensors.bag')) as b:
 for _,m,_ in b.read_messages(topics=['/go2w_lio/cloud']):
  if not m.width*m.height:continue
  if m.header.frame_id!='camera_init':raise ValueError('Unexpected map frame')
  fs={f.name:f for f in m.fields};color='rgb' if 'rgb' in fs else 'rgba'
  if color not in fs:raise ValueError('No registered RGB field')
  endian='>' if m.is_bigendian else '<';dt=np.dtype(dict(names=['x','y','z','rgb'],formats=[endian+'f4']*3+[endian+'u4'],offsets=[fs[k].offset for k in ['x','y','z',color]],itemsize=m.point_step))
  pts=np.ndarray((m.height,m.width),dtype=dt,buffer=m.data,strides=(m.row_step,m.point_step)).ravel();xyz=np.column_stack([pts[k] for k in ['x','y','z']]);mask=np.isfinite(xyz).all(1);xyz=xyz[mask];rgb=pts['rgb'][mask];keys=np.floor(xyz/a.voxel).astype(np.int64);_,inds=np.unique(keys.view(np.dtype((np.void,keys.dtype.itemsize*3))).ravel(),return_index=True)
  for i in inds:
   key=tuple(keys[i])
   if key not in voxels:voxels[key]=(*map(float,xyz[i]),int(rgb[i]))
  if len(voxels)>3000000:raise RuntimeError('Map exceeds exporter memory guard')
  frames+=1;input_points+=len(xyz)
pts=np.array(list(voxels.values()),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')]);n=len(pts)
name='map_rgb_'+str(round(a.voxel*1000))+'mm.pcd';header=f'# .PCD v0.7\nVERSION 0.7\nFIELDS x y z rgb\nSIZE 4 4 4 4\nTYPE F F F U\nCOUNT 1 1 1 1\nWIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {n}\nDATA binary\n'
with (root/name).open('wb') as f:f.write(header.encode());f.write(pts.tobytes())
result=dict(voxel_m=a.voxel,map_points=n,source_points=input_points,nonempty_frames=frames,frame='camera_init',rgb_preserved=True,ground_truth_available=False)
(root/(Path(name).stem+'_result.json')).write_text(json.dumps(result,indent=2))
if abs(a.voxel-.02)<1e-9:(root/'rgb_map_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
if not n:raise SystemExit(1)
