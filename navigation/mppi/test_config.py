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
 def test_lateral_correction_keeps_heading_guidance_outside_goal_circle(self):
  import runpy
  root=Path(__file__).resolve().parent
  configs=[self.p,yaml.safe_load((root/'demo_nav.yaml').read_text()),runpy.run_path(str(root/'make_config.py'))['p']]
  for config in configs:
   c=config['controller_server']['ros__parameters'];f=c['FollowPath']
   # The recorded stall at 8.56 cm must still have goal-bearing guidance and
   # must not already be asked to hold the final yaw while lateral error remains.
   self.assertGreater(.0855983569,f['PathAngleCritic']['threshold_to_consider'])
   self.assertGreater(.0855983569,f['GoalAngleCritic']['threshold_to_consider'])
   switch=f['GoalAngleCritic']['threshold_to_consider']
   self.assertGreater(switch,0.)
   self.assertLess(switch,c['goal_checker']['xy_goal_tolerance'])
   self.assertEqual(switch,f['PathAngleCritic']['threshold_to_consider'])
   self.assertTrue(f['PathAngleCritic']['forward_preference'])
   self.assertNotIn('mode',f['PathAngleCritic'])
 def test_prediction_interval_matches_controller(self):
  c=self.p['controller_server']['ros__parameters'];self.assertAlmostEqual(c['FollowPath']['model_dt'],1/c['controller_frequency'])
 def test_action_ack_timeout_survives_config_regeneration(self):
  import runpy
  root=Path(__file__).resolve().parent
  configs=[self.p,yaml.safe_load((root/'demo_nav.yaml').read_text()),runpy.run_path(str(root/'make_config.py'))['p']]
  for config in configs:
   bt=config['bt_navigator']['ros__parameters']
   self.assertEqual(bt['default_server_timeout'],1000)
   self.assertEqual(bt['bt_loop_duration'],10)
 def test_same_time_and_footprint(self):
  maps=[self.p[n][n]['ros__parameters'] for n in ('local_costmap','global_costmap')]
  self.assertEqual(maps[0]['footprint'],maps[1]['footprint'])
  for c in maps:self.assertTrue(c['use_sim_time']);self.assertTrue(c['track_unknown_space']);self.assertTrue(c['obstacle_layer']['lidar']['clearing'])
 def test_clearance_matches_guard_and_inflation_covers_corners(self):
  import importlib.util,json,math
  root=Path(__file__).resolve().parents[1]
  spec=importlib.util.spec_from_file_location('clearance_policy',root/'nav2/motion_policy.py');policy=importlib.util.module_from_spec(spec)
  import sys
  sys.path.insert(0,str(root/'nav2'))
  try:spec.loader.exec_module(policy)
  finally:sys.path.pop(0)
  for path in (root/'nav2/floor.yaml',root/'mppi/params.yaml',root/'mppi/demo_nav.yaml'):
   config=yaml.safe_load(path.read_text())
   for key in ('global_costmap','local_costmap'):
    k=config[key][key]['ros__parameters'];points=json.loads(k['footprint']);pad=k['footprint_padding']
    self.assertAlmostEqual(pad,.1)
    self.assertAlmostEqual(max(abs(p[0]) for p in points)+pad,policy.HALF_LENGTH)
    self.assertAlmostEqual(max(abs(p[1]) for p in points)+pad,policy.HALF_WIDTH)
    self.assertGreaterEqual(k['inflation_layer']['inflation_radius'],math.hypot(policy.HALF_LENGTH,policy.HALF_WIDTH))
if __name__=='__main__':unittest.main()
