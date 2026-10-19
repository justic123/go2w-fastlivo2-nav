import unittest
from startup_gate import StartupGate
class StartupTests(unittest.TestCase):
 def test_transient_cold_start_waits_for_continuous_good_input(self):
  g=StartupGate(0)
  self.assertFalse(g.observe(1,True,False));self.assertFalse(g.observe(2,False,True))
  self.assertFalse(g.observe(3,True,True));self.assertFalse(g.observe(3.5,False,True))
  self.assertFalse(g.observe(4,True,True));self.assertTrue(g.observe(5,True,True))
 def test_timeout_is_bounded(self):
  g=StartupGate(0)
  with self.assertRaisesRegex(RuntimeError,'未能稳定'):g.observe(41,False,False)
if __name__=='__main__':unittest.main()
