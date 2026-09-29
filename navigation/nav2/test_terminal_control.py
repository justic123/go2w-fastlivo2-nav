import unittest,math
from terminal_control import TerminalAlignment
class TerminalTests(unittest.TestCase):
 def settled(self,target_yaw=1.):
  c=TerminalAlignment((0,0),target_yaw,0)
  for i in range(9):v,done=c.step((0,0,0,i*.1),i*.1);self.assertEqual(v,(0,0,0));self.assertFalse(done)
  return c
 def test_settle_then_bounded_pure_rotation(self):
  c=self.settled();v,done=c.step((0,0,0,1.1),1.1);self.assertEqual(v,(0,0,.25));self.assertFalse(done)
 def test_duplicates_do_not_claim_settled(self):
  c=TerminalAlignment((0,0),0,0)
  for i in range(50):self.assertFalse(c.step((0,0,0,1),i*.1)[1])
 def test_drift_aborts(self):
  c=self.settled()
  with self.assertRaises(ValueError):c.step((.11,0,0,1.2),1.2)
 def test_yaw_wrap_and_completion(self):
  c=TerminalAlignment((0,0),-math.pi+.02,0)
  for i in range(30):v,done=c.step((0,0,math.pi-.02,i*.1),i*.1)
  self.assertTrue(done);self.assertEqual(v,(0,0,0))
 def test_timeout(self):
  c=self.settled()
  with self.assertRaises(ValueError):c.step((0,0,0,36),36)
