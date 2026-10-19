import unittest,struct
from types import SimpleNamespace as N
import numpy as np
from rgb_cloud import decode,Accumulator
class RGBTests(unittest.TestCase):
 def test_packed_float_color_padded_rows_endian(self):
  for endian in ('<','>'):
   data=struct.pack(endian+'fffII',1,2,3,0,0xFF8020)+bytes(12)
   m=N(header=N(frame_id='camera_init'),width=1,height=1,is_bigendian=endian=='>',point_step=20,row_step=32,data=data,fields=[N(name=k,offset=o,datatype=7) for k,o in [('x',0),('y',4),('z',8),('rgb',16)]])
   np.testing.assert_allclose(decode(m),[[1,2,3,1,128/255,32/255]],atol=1e-6)
 def test_bounded_accumulation(self):
  a=Accumulator(limit=10);a.add(np.array([[i*.02,0,0,1,0,0] for i in range(100)]));self.assertLessEqual(len(a.array()),10);self.assertGreater(a.voxel,.02)
 def test_empty_is_ignored(self):
  self.assertEqual(len(decode(N(header=N(frame_id='camera_init'),width=0,height=0,fields=[]))),0)
if __name__=='__main__':unittest.main()
