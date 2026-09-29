import math,unittest
from point_policy import velocity,endpoint_metrics
class PolicyTest(unittest.TestCase):
 def test_rotated_start(self):
  vx,w,done=velocity((2,3,math.pi/2),(2,3.15,math.pi/2));self.assertGreater(vx,0);self.assertEqual(w,0);self.assertFalse(done)
 def test_reached(self):self.assertTrue(velocity((0,0,0),(.28,0,0))[2])
 def test_lateral_escape(self):
  with self.assertRaises(ValueError):velocity((0,0,0),(.1,.11,0))
 def test_heading_escape(self):
  with self.assertRaises(ValueError):velocity((0,0,0),(0,0,.3))
 def test_nan(self):
  with self.assertRaises(ValueError):velocity((0,0,0),(math.nan,0,0))
 def test_overshoot(self):
  with self.assertRaises(ValueError):velocity((0,0,0),(.5,0,0))
 def test_point_holds_starting_speed(self):
  self.assertEqual(velocity((0,0,0),(.20,0,0),.3,.1,True)[0],.1)
 def test_point_stops_at_threshold(self):
  self.assertEqual(velocity((0,0,0),(.27,0,0),.3,.1,True),(0.,0.,True))
 def test_speed_limit(self):
  for speed in [.10001,float('nan')]:
   with self.assertRaises(ValueError):velocity((0,0,0),(0,0,0),.3,speed,True)
class EndpointTest(unittest.TestCase):
 def test_rotated_endpoint(self):
  r=endpoint_metrics((2,3,math.pi/2),(1.98,3.49,math.pi/2),.5)
  self.assertAlmostEqual(r['along_m'],.49);self.assertAlmostEqual(r['cross_m'],.02)
  self.assertAlmostEqual(r['goal_error_m'],math.hypot(.01,.02))
 def test_wrapped_heading(self):
  r=endpoint_metrics((0,0,math.pi-.01),(0,0,-math.pi+.01),.5)
  self.assertAlmostEqual(r['heading_error_deg'],math.degrees(.02))
 def test_half_metre_goal(self):
  self.assertFalse(velocity((0,0,0),(.40,0,0),.5,.1,True)[2])
  self.assertTrue(velocity((0,0,0),(.47,0,0),.5,.1,True)[2])
if __name__=='__main__':unittest.main()
