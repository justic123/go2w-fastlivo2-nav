import unittest
from backlog_policy import BacklogGuard
class BacklogTests(unittest.TestCase):
 def test_transient_recovery_no_reset(self):
  g=BacklogGuard();self.assertEqual(g.check(1.02,0),'catching_up');self.assertEqual(g.check(.15,1),'live');self.assertEqual(g.check(1.1,10),'catching_up');self.assertEqual(g.check(.15,11),'live')
 def test_sustained_and_hard_stop(self):
  g=BacklogGuard();g.check(1.2,0)
  with self.assertRaises(RuntimeError):g.check(1.2,5.1)
  with self.assertRaises(RuntimeError):BacklogGuard().check(3.,0)
 def test_future_nan_rejected(self):
  for a in [-.2,float('nan')]:
   with self.assertRaises(RuntimeError):BacklogGuard().check(a,0)
