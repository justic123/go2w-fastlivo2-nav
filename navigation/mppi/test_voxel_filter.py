import unittest,numpy as np
from voxel_filter import voxel_indices
class Filtering(unittest.TestCase):
 def test_identical_first_points_including_negative_coordinates(self):
  rng=np.random.default_rng(42);p=rng.uniform(-90,90,(5000,3)).astype(np.float32)
  p=np.concatenate([p,p,p+1e-5,np.array([[-.05,0,0],[0,0,0],[.05,0,0],[-.050001,0,0]],dtype=np.float32)])
  original=np.unique(np.floor(p/.05).astype(np.int32),axis=0,return_index=True)[1]
  np.testing.assert_array_equal(voxel_indices(p),np.sort(original))
 def test_empty_and_noncontiguous(self):
  self.assertEqual(len(voxel_indices(np.empty((0,3),dtype=np.float32))),0)
  p=np.arange(60,dtype=np.float32).reshape(10,6)[:,::2]
  np.testing.assert_array_equal(voxel_indices(p),np.arange(10))
 def test_integer_encoding_edges_and_fallback(self):
  for cells in ([[-1048576,0,0],[1048575,0,0],[0,-1048576,1048575],[0,0,0]],
                [[-1048577,0,0],[1048576,0,0],[0,1048576,0]]):
   p=np.array(cells,dtype=np.float64)*.05;p=np.concatenate([p,p])
   expected=np.sort(np.unique(np.floor(p/.05).astype(np.int32),axis=0,return_index=True)[1])
   np.testing.assert_array_equal(voxel_indices(p),expected)
if __name__=='__main__':unittest.main()
