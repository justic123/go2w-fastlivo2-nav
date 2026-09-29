"""Recover the immutable point map from the historical bag, up to its frozen-map time."""
import rosbag,rospy,numpy as np,json,time
from pathlib import Path
bag='/work/runs/desktop-20260928-230235/sensors.bag'
offset=json.loads(Path('/work/runs/desktop-20260928-230235/transport.json').read_text())['clock_offset'];cutoff=offset+1129181.604082944
chunks=[];last=-1e30;n=0
with rosbag.Bag(bag) as b:
 for topic,m,rt in b.read_messages(topics=['/go2w_lio/cloud']):
  t=m.header.stamp.to_sec()
  if t>cutoff:break
  if m.width*m.height==0 or t-last<.5:continue
  if m.header.frame_id!='camera_init':raise ValueError('unexpected historical frame')
  fs={f.name:f for f in m.fields}
  dt=np.dtype(dict(names=['x','y','z'],formats=['<f4']*3,offsets=[fs[k].offset for k in ('x','y','z')],itemsize=m.point_step))
  a=np.ndarray((m.height,m.width),dtype=dt,buffer=m.data,strides=(m.row_step,m.point_step));xyz=np.column_stack([a[k].ravel() for k in ('x','y','z')]);xyz=xyz[np.isfinite(xyz).all(1)]
  _,i=np.unique(np.floor(xyz/.08).astype(np.int32),axis=0,return_index=True);chunks.append(xyz[i]);last=t;n+=1
  if n%100==0:print('frames',n,flush=True)
a=np.concatenate(chunks);_,i=np.unique(np.floor(a/.08).astype(np.int32),axis=0,return_index=True);a=a[i];np.save('/tmp/old_map.npy',a)
Path('/tmp/old_map.json').write_text(json.dumps(dict(session='desktop-20260928-230235',frame='map',frames=n,points=len(a),voxel=.08,cutoff=cutoff,source=bag)))
print('done',len(a),flush=True)
