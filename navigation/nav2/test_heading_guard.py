import unittest,math
from heading_guard import check_heading,imu_delta,is_level
class HeadingTests(unittest.TestCase):
 def history(self,rate):return [[i*.002,0.,0.,rate] for i in range(151)]
 def test_recorded_trigger_requires_independent_imu(self):
  dt=.20185804297216237;delta=-.20423408849463257
  a=(0,0,0,0);b=(0,0,delta,dt)
  with self.assertRaises(ValueError):check_heading(a,b)
  d=check_heading(a,b,self.history(delta/dt),True);self.assertLess(abs(d['residual']),1e-6)
 def test_disagreeing_imu_rejected(self):
  with self.assertRaises(ValueError):check_heading((0,0,0,0),(0,0,.21,.2),self.history(0),True)
 def test_gap_and_missing_coverage_rejected(self):
  h=self.history(1.05)
  for samples in [h[:70],h[10:],h[:40]+h[70:]]:
   with self.assertRaises(ValueError):check_heading((0,0,0,0),(0,0,.21,.2),samples,True)
 def test_rate_and_long_interval_rejected(self):
  for angle,dt in [(.21,.1),(.21,.3)]:
   with self.assertRaises(ValueError):check_heading((0,0,0,0),(0,0,angle,dt),self.history(angle/dt),True)
 def test_wrap(self):check_heading((0,0,math.pi-.02,0),(0,0,-math.pi+.02,.1))
 def test_tilt_rejects_extension(self):
  self.assertTrue(is_level((0,0,0,1)))
  self.assertFalse(is_level((math.sin(.2/2),0,0,math.cos(.2/2))))
  with self.assertRaises(ValueError):check_heading((0,0,0,0),(0,0,.21,.2),self.history(1.05),False)
 def test_trapezoid_interpolated_boundaries(self):
  h=[[0.,0,0,0],[.01,0,0,1],[.02,0,0,2]]
  self.assertAlmostEqual(imu_delta(h,.002,.008),.003)
 def test_invalid_history(self):
  h=self.history(1.)
  h[1][3]=float('nan')
  with self.assertRaises(ValueError):imu_delta(h,0,.2)
if __name__=='__main__':unittest.main()
