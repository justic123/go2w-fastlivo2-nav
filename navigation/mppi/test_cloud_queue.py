import unittest
from cloud_queue import select_cloud
class QueuePolicy(unittest.TestCase):
 def test_continuous_odom_does_not_starve_already_covered_cloud(self):
  history=[(10.,100.),(10.02,100.02),(10.04,100.04)]
  chosen,_=select_cloud([('scan',10.,100.)],10.04,100.045,100.04,tf_history=history)
  self.assertEqual(chosen[0],'scan')
 def test_published_tf_can_release_cloud_without_artificial_wait(self):
  waiting=[('scan',10.04,100.04)]
  history=[(10.,100.),(10.04,100.04)]
  self.assertEqual(select_cloud(waiting,10.04,100.045,100.04,tf_history=history)[0][1],10.04)
  self.assertIsNone(select_cloud([('future',10.05,100.04)],10.04,100.045,100.04,tf_history=history)[0])
  self.assertEqual(select_cloud(waiting,10.04,100.08,100.04,tf_history=history)[0][1],10.04)
 def test_only_newest_covered_scan_and_future_retained(self):
  items=[('old',10,100),('new',11,100),('future',12,100)]
  chosen,remaining=select_cloud(items,11,100.1,100)
  self.assertEqual(chosen[0],'new');self.assertEqual(remaining,[items[2]])
 def test_no_future_tf_or_expired_receipt(self):
  self.assertEqual(select_cloud([('x',12,99)],11,100,99),(None,[]))
  self.assertEqual(select_cloud([('x',12,100)],11,100.1,100)[0],None)
 def test_tf_delivery_wait_and_duplicate_scans(self):
  items=[('a',10,100),('b',10,100)]
  self.assertIsNone(select_cloud(items,10,100.01,100,delivery_wait=.025)[0])
  chosen,remaining=select_cloud(items,10,100.1,100);self.assertIsNotNone(chosen);self.assertEqual(remaining,[])
if __name__=='__main__':unittest.main()
