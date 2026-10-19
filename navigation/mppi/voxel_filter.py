"""Same first point per 5 cm cell, with one fixed-width key per XYZ triplet."""
import numpy as np

def voxel_indices(xyz,size=.05):
    if len(xyz)==0:return np.empty(0,dtype=np.intp)
    keys=np.ascontiguousarray(np.floor(xyz/size).astype(np.int32))
    # Integer sorting is substantially cheaper on the board than sorting opaque
    # 12-byte records. Encode all three signed coordinates without collisions;
    # keep the general fallback for coordinates outside the 21-bit range.
    if keys.min()>=-(1<<20) and keys.max()<(1<<20):
        shifted=keys.astype(np.int64)+(1<<20)
        packed=(shifted[:,0]<<42)|(shifted[:,1]<<21)|shifted[:,2]
    else:
        packed=keys.view(np.dtype((np.void,keys.dtype.itemsize*3))).ravel()
    # Sort selected indices, not the whole cloud. Consumers do not need voxel order.
    return np.sort(np.unique(packed,return_index=True)[1])
