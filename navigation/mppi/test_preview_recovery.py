import unittest
from preview_recovery import wait_healthy

class Recovery(unittest.TestCase):
 def setUp(self):self.now=0.;self.checks=0
 def pump(self):self.now+=.05
 def clock(self):return self.now
 def test_healthy_returns_without_wait(self):
  self.assertEqual(wait_healthy(lambda:42,pump=self.pump,clock=self.clock),42);self.assertEqual(self.now,0.)
 def test_transient_must_recover_stably(self):
  def check():
   self.checks+=1
   if self.now<.2 or .3<self.now<.45:raise RuntimeError('stale')
   return 42
  self.assertEqual(wait_healthy(check,pump=self.pump,clock=self.clock),42);self.assertGreaterEqual(self.now,.65)
 def test_permanent_failure_times_out_with_reason(self):
  def check():raise RuntimeError('cloud_age=2')
  with self.assertRaisesRegex(RuntimeError,'cloud_age=2'):wait_healthy(check,pump=self.pump,clock=self.clock,timeout=.4)
  self.assertLess(self.now,.5)
if __name__=='__main__':unittest.main()
