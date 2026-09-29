import math,unittest
from staged_heading import HeadingAlignment,path_heading
from terminal_control import TerminalAlignment,PositionRecoveryRequired
class Tests(unittest.TestCase):
 def test_right_turn_shortest_direction_no_forward(self):
  h=HeadingAlignment(0,(0,0,math.pi/4,0),0)
  v,done=h.step((0,0,math.pi/4,.1),.1)
  self.assertEqual(v[:2],(0,0));self.assertLess(v[2],0);self.assertLessEqual(abs(v[2]),.5);self.assertFalse(done)
 def test_wrap_does_not_choose_full_circle(self):
  h=HeadingAlignment(-math.pi+.2,(0,0,math.pi-.2,0),0)
  self.assertGreater(h.step((0,0,math.pi-.2,.1),.1)[0][2],0)
 def test_must_settle_distinct_measurements(self):
  h=HeadingAlignment(0,(0,0,0,0),0)
  for i in range(10):self.assertFalse(h.step((0,0,0,0),i*.1)[1])
  for i in range(1,7):v,done=h.step((0,0,.01,i*.1),1+i*.1)
  self.assertTrue(done);self.assertEqual(v,(0,0,0))
 def test_turn_drift_and_timeout_stop(self):
  for p,t in [((.41,0,0,.1),.1),((0,0,0,31),31)]:
   with self.assertRaises(ValueError):HeadingAlignment(1,(0,0,0,0),0).step(p,t)
 def test_path_heading_uses_path_not_direct_target(self):
  self.assertAlmostEqual(path_heading([(0,0),(0,.6),(1,1)],(0,0,0,0)),math.pi/2)
 def test_terminal_drift_requests_position_replan_not_success(self):
  c=TerminalAlignment((0,0),0,0)
  with self.assertRaises(PositionRecoveryRequired):c.step((.11,0,.7,1),1)
if __name__=='__main__':unittest.main()
