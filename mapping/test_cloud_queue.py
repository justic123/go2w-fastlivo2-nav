import queue,unittest
from cloud_queue import offer_latest,stale_cloud
class Tests(unittest.TestCase):
 def test_overload_keeps_recent_order(self):
  q=queue.Queue(2);n=sum(offer_latest(q,x) for x in range(10))
  self.assertEqual(n,8);self.assertEqual([q.get_nowait(),q.get_nowait()],[8,9])
 def test_normal_input_unchanged(self):
  q=queue.Queue(2);self.assertEqual(offer_latest(q,('stamp',123)),0);self.assertEqual(q.get_nowait(),('stamp',123))
 def test_age_uses_original_stamp(self):
  self.assertFalse(stale_cloud(10,9.6));self.assertTrue(stale_cloud(10,9.49))
if __name__=='__main__':unittest.main()
