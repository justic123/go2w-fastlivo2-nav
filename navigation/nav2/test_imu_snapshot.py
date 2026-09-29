import unittest
from imu_snapshot import select_snapshot
class SnapshotTests(unittest.TestCase):
 def test_future_waits_preserves_receipt(self):
  rows=[dict(stamp=1.,receipt=.999),dict(stamp=1.01,receipt=1.001)]
  h=[[1.,0,0,0],[1.01,0,0,0]]
  a=select_snapshot(rows,h,1.005,None)
  self.assertEqual(a['stamp'],1.);self.assertEqual(a['receipt'],.999);self.assertEqual(len(a['history']),1)
  self.assertEqual(select_snapshot(rows,h,1.02,None)['stamp'],1.01)
 def test_no_future_or_fault_hidden(self):
  self.assertIsNone(select_snapshot([dict(stamp=2.,receipt=1.)],[],1.5,None))
  self.assertEqual(select_snapshot([dict(stamp=1.,receipt=1.)],[],3.,'gap')['fault'],'gap')
if __name__=='__main__':unittest.main()
