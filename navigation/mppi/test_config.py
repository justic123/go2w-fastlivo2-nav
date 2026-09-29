"""Cross-layer invariants: a controller must not predict motion the output rejects."""
import unittest,yaml
from pathlib import Path
class Configuration(unittest.TestCase):
 def setUp(self):self.p=yaml.safe_load(Path(__file__).with_name('params.yaml').read_text())
 def test_velocity_contract(self):
  c=self.p['controller_server']['ros__parameters']['FollowPath'];s=self.p['velocity_smoother']['ros__parameters']
  self.assertEqual(c['vx_max'],s['max_velocity'][0]);self.assertEqual(c['vx_min'],s['min_velocity'][0]);self.assertEqual(c['vy_max'],s['max_velocity'][1]);self.assertEqual(c['wz_max'],s['max_velocity'][2]);self.assertEqual(-c['wz_max'],s['min_velocity'][2])
 def test_no_stateful_position_latch(self):
  c=self.p['controller_server']['ros__parameters'];self.assertFalse(c['goal_checker']['stateful']);self.assertEqual(c['controller_plugins'],['FollowPath'])
 def test_prediction_interval_matches_controller(self):
  c=self.p['controller_server']['ros__parameters'];self.assertAlmostEqual(c['FollowPath']['model_dt'],1/c['controller_frequency'])
 def test_same_time_and_footprint(self):
  maps=[self.p[n][n]['ros__parameters'] for n in ('local_costmap','global_costmap')]
  self.assertEqual(maps[0]['footprint'],maps[1]['footprint'])
  for c in maps:self.assertTrue(c['use_sim_time']);self.assertTrue(c['track_unknown_space']);self.assertTrue(c['obstacle_layer']['lidar']['clearing'])
if __name__=='__main__':unittest.main()
