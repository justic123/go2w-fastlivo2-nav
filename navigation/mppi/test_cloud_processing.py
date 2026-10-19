import unittest,numpy as np
from cloud_processing import prepare_cloud

class Clouds(unittest.TestCase):
 def test_padded_rows_endianness_and_invalid_points(self):
  for endian in ('<','>'):
   data=bytearray(64)
   dtype=np.dtype(dict(names=['x','y','z'],formats=[endian+'f4']*3,offsets=[0,4,8],itemsize=12))
   a=np.ndarray((2,2),dtype=dtype,buffer=data,strides=(32,12))
   a['x']=[[1,1],[2,np.nan]];a['y']=0;a['z']=.2
   header=dict(fields=[[k,i*4,7,1] for i,k in enumerate('xyz')],bigendian=endian=='>',height=2,width=2,row_step=32,point_step=12)
   out=prepare_cloud(header,data)
   np.testing.assert_allclose(out,[[1,0,.2],[2,0,.2]])
   self.assertEqual(out.dtype,np.dtype('<f4'))
 def test_reject_bad_format(self):
  with self.assertRaises(ValueError):prepare_cloud(dict(fields=[[k,i*4,8,1] for i,k in enumerate('xyz')]),b'')
if __name__=='__main__':unittest.main()
