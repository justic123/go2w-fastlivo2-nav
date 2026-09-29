import unittest,math
from odom_twist import planar_twist
def pose(t,a,x=0,y=0):return dict(stamp=t,pose=[x,y,0,0,0,math.sin(a/2),math.cos(a/2)])
class TwistTests(unittest.TestCase):
 def test_turn_both_directions(self):
  for w in [-.2,.2]:self.assertAlmostEqual(planar_twist(pose(1,0),pose(1.1,w*.1))[2],w)
 def test_wrap(self):self.assertAlmostEqual(planar_twist(pose(1,math.pi-.01),pose(1.1,-math.pi+.01))[2],.2)
 def test_body_frame(self):
  x,y,w=planar_twist(pose(1,math.pi/2),pose(2,math.pi/2,y=.1));self.assertAlmostEqual(x,.1);self.assertAlmostEqual(y,0);self.assertEqual(w,0)
