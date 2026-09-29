"""Bounded voxel accumulation for display only; never feeds robot estimation."""
import numpy as np
class DisplayMap:
 def __init__(self,voxel=.02,limit=750000):self.voxel=voxel;self.limit=limit;self.points={};self.capped=False;self.coarsenings=0
 def add(self,m,data):
  if not m['width'] or not m['height'] or not data:return False
  fs={f[0]:f for f in m['fields']}
  if any(k not in fs or fs[k][2]!=7 for k in ('x','y','z')):raise ValueError('Expected XYZ float32')
  endian='>' if m['is_bigendian'] else '<'
  names=['x','y','z'];formats=[endian+'f4']*3;offsets=[fs[k][1] for k in names]
  color='rgb' if 'rgb' in fs else 'rgba' if 'rgba' in fs else None
  if color:names+=['color'];formats+=[endian+'u4'];offsets+=[fs[color][1]]
  dt=np.dtype(dict(names=names,formats=formats,offsets=offsets,itemsize=m['point_step']))
  a=np.ndarray((m['height'],m['width']),dtype=dt,buffer=data,strides=(m['row_step'],m['point_step'])).ravel()
  xyz=np.column_stack([a[k] for k in ('x','y','z')]);valid=np.isfinite(xyz).all(1);xyz=xyz[valid];colors=a['color'][valid] if color else np.full(len(xyz),0xaaaaaa,dtype=np.uint32)
  for p,c in zip(xyz,colors):
   key=tuple(np.floor(p/self.voxel).astype(np.int64))
   if key not in self.points:
    if len(self.points)>=self.limit:
     # Keep whole-floor coverage: merge display voxels, never clear or freeze the map.
     self.voxel*=2;self.coarsenings+=1;merged={}
     for value in self.points.values():merged.setdefault(tuple(int(np.floor(v/self.voxel)) for v in value[:3]),value)
     self.points=merged;key=tuple(np.floor(p/self.voxel).astype(np.int64));self.capped=False
    self.points[key]=(float(p[0]),float(p[1]),float(p[2]),int(c))
  return True
 def packed(self):
  a=np.array(list(self.points.values()),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')]);return a.tobytes(),len(a)
