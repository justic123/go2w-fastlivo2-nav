import unittest
from motion_policy import check_health,check_command,check_pose,swept_clear
class SafetyTests(unittest.TestCase):
 def test_command_limits(self):
  self.assertEqual(check_command((.1,0,.1),.1),(.1,0.,.1))
  for cmd,age in [((.101,0,0),.1),((-.01,0,0),.1),((0,.01,0),.1),((0,0,.8001),.1),((float('nan'),0,0),.1),((.1,0,0),.36)]:
   with self.assertRaises(ValueError):check_command(cmd,age)
 def test_floor_forward_limit(self):
  self.assertEqual(check_command((.2,0,0),.1,.2),(.2,0.,0.))
  self.assertEqual(check_command((.2+2e-16,0,0),.1,.2),(.2,0.,0.))
  for x,limit in [(.2001,.2),(.1001,.1),(-.01,.2)]:
   with self.assertRaises(ValueError):check_command((x,0,0),.1,limit)
 def test_yaw_limit_both_directions(self):
  for w in [-.8,.8]:self.assertEqual(check_command((0,0,w),.1),(0,0.,w))
  for w in [-.8001,.8001]:
   with self.assertRaises(ValueError):check_command((0,0,w),.1)
 def test_roundoff_clamps_to_exact_yaw_limit(self):
  for sign in [-1,1]:
   self.assertEqual(check_command((0,0,sign*(.8+2e-16)),.1),(0,0.,sign*.8))
 def test_health(self):
  h=dict(last_check=10,pose_age_s=.1,cloud_age_s=.2);check_health(h,10.1)
  for k,v in [('last_check',9),('pose_age_s',None),('cloud_age_s',.81),('pose_age_s',float('nan'))]:
   with self.assertRaises(ValueError):check_health(dict(h,**{k:v}),10.1)
 def test_jump(self):
  check_pose((0,0,0,1),(.01,0,0,1.1))
  for v in [(.2,0,0,1.1),(0,0,.3,1.1),(0,0,0,.9)]:
   with self.assertRaises(ValueError):check_pose((0,0,0,1),v)
 def test_faster_swept_obstacle(self):
  data=[0]*6400;grid=(data,80,80,.05,-2,-2)
  data[40*80+55]=100
  with self.assertRaises(ValueError):swept_clear(grid,(0,0,0),(.2,0,0))
 def test_costmap(self):
  data=[0]*1600;grid=(data,40,40,.1,-2,-2);swept_clear(grid,(0,0,0),(.1,0,0))
  for value in [-1,100]:
   data[20*40+25]=value
   with self.assertRaises(ValueError):swept_clear(grid,(0,0,0),(.1,0,0))
  data[20*40+25]=0
  with self.assertRaises(ValueError):swept_clear(grid,(1.8,0,0),(.1,0,0))
if __name__=='__main__':unittest.main()
