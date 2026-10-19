"""Display-only RGB extraction/accumulation. Does not change SLAM or navigation."""
import math
import numpy as np

def decode(m):
    fields={f.name:f for f in m.fields};color='rgb' if 'rgb' in fields else 'rgba'
    if m.header.frame_id!='camera_init' or not m.width*m.height:return np.empty((0,6),dtype='<f4')
    if any(k not in fields for k in ('x','y','z',color)):raise ValueError('Missing RGB fields')
    if any(fields[k].datatype!=7 for k in ('x','y','z')) or fields[color].datatype not in (6,7):raise ValueError('Unexpected RGB layout')
    endian='>' if m.is_bigendian else '<'
    dt=np.dtype(dict(names=['x','y','z','rgb'],formats=[endian+'f4']*3+[endian+'u4'],offsets=[fields[k].offset for k in ('x','y','z',color)],itemsize=m.point_step))
    pts=np.ndarray((m.height,m.width),dtype=dt,buffer=m.data,strides=(m.row_step,m.point_step)).ravel()[::max(1,math.ceil(m.width*m.height/48000))]
    xyz=np.column_stack([pts[k] for k in ('x','y','z')]);rgb=pts['rgb'];a=np.column_stack([xyz,(rgb>>16)&255,(rgb>>8)&255,rgb&255]).astype('<f4');a[:,3:]/=255
    return a[np.isfinite(a).all(1)]

class Accumulator:
    def __init__(self,limit=400000):self.points={};self.voxel=.02;self.limit=limit
    def add(self,a):
        keys=np.floor(a[:,:3]/self.voxel).astype(np.int64)
        _,inds=np.unique(keys,axis=0,return_index=True)
        for i in inds:self.points[tuple(keys[i])]=a[i].copy()
        while len(self.points)>self.limit:
            self.voxel*=1.5
            self.points={tuple(np.floor(p[:3]/self.voxel).astype(np.int64)):p for p in self.points.values()}
    def array(self):return np.asarray(list(self.points.values()),dtype='<f4').reshape(-1,6)
