import unittest
import numpy as np
from input_core import RAW,EXPECTED,convert_cloud,TickClock
class Checks(unittest.TestCase):
 def test_unsorted_packed_cloud_and_end_header(self):
  a=np.zeros(3,dtype=RAW);a['x']=[1,2,3];a['ring']=[0,15,1];a['time']=[100e6,0,50e6]
  m=dict(fields=list(EXPECTED),bigendian=False,point_step=22,row_step=66,height=1,width=3,stamp_sec=100,stamp_nanosec=0)
  b,s,e,d=convert_cloud(m,a.tobytes(),'ns','end')
  np.testing.assert_array_equal(b['x'],[2,3,1]);self.assertAlmostEqual(s,99.9);self.assertAlmostEqual(e,100);self.assertEqual(d,0)
  with self.assertRaises(ValueError):convert_cloud(m,a.tobytes()[:-1],'ns','end')
  with self.assertRaises(ValueError):convert_cloud(m,a.tobytes(),'guess','end')
  m['fields']=list(EXPECTED-{('time',7,18,1)})
  with self.assertRaises(ValueError):convert_cloud(m,a.tobytes(),'ns','end')
 def test_filtering_preserves_scan_time_reference(self):
  a=np.zeros(3,dtype=RAW);a['x']=[1,2,np.nan];a['time']=[0,50e6,100e6]
  m=dict(fields=list(EXPECTED),bigendian=False,point_step=22,row_step=66,height=1,width=3,stamp_sec=100,stamp_nanosec=0)
  b,s,e,d=convert_cloud(m,a.tobytes(),'ns','end')
  self.assertAlmostEqual(s,99.9);self.assertAlmostEqual(e,99.95);self.assertEqual(d,1)
 def test_tick_duplicate_and_reset(self):
  c=TickClock(warmup=3)
  self.assertIsNone(c.observe(100,10));self.assertIsNone(c.observe(102,10.002));self.assertIsNone(c.observe(102,10.1));self.assertAlmostEqual(c.observe(104,10.004),10.004);self.assertEqual(c.duplicates,1)
  self.assertAlmostEqual(c.observe(106,10.2),10.006)
  with self.assertRaises(ValueError):c.observe(0,10.201)
if __name__=='__main__':unittest.main()
