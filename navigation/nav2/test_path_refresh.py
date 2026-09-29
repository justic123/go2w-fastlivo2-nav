import unittest
from path_refresh import needs_refresh
class RefreshTest(unittest.TestCase):
 def test_stationary_resampled_path_keeps_critic_state(self):
  self.assertFalse(needs_refresh([(0,0),(.5,.01),(1,0)],[(0,0),(1,0)],(0,0),(0,0)))
 def test_obstacle_detour_refreshes_even_stationary(self):
  self.assertTrue(needs_refresh([(0,0),(.5,.3),(1,0)],[(0,0),(1,0)],(0,0),(0,0)))
 def test_progress_refreshes(self):
  self.assertTrue(needs_refresh([(.3,0),(1,0)],[(0,0),(1,0)],(.3,0),(0,0)))
if __name__=='__main__':unittest.main()
