"""Prepare navigation clouds before waiting for fusion TF; preserve source stamps."""
import numpy as np
from voxel_filter import voxel_indices

def prepare_cloud(d,raw):
    fs={f[0]:f for f in d['fields']}
    if any(fs[k][2]!=7 for k in ('x','y','z')):
        raise ValueError('Unexpected cloud format')
    dtype=np.dtype(dict(names=['x','y','z'],formats=[('>' if d['bigendian'] else '<')+'f4']*3,
                       offsets=[fs[k][1] for k in ('x','y','z')],itemsize=d['point_step']))
    arr=np.ndarray((d['height'],d['width']),dtype=dtype,buffer=raw,
                   strides=(d['row_step'],d['point_step']))
    xyz=np.column_stack([arr[k].ravel() for k in ('x','y','z')]).astype('<f4',copy=False)
    xyz=xyz[np.isfinite(xyz).all(axis=1)]
    return xyz[voxel_indices(xyz)]
