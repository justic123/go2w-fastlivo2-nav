import importlib.util,json,tempfile,unittest,subprocess,shutil,sys
from pathlib import Path
from speed_profiles import profile,from_config,PROFILES,source_age_limit
import yaml
class Profiles(unittest.TestCase):
 def config(self,name):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'mppi').mkdir();(r/'nav2').mkdir()
   for f in ['make_config.py','speed_profiles.py']:shutil.copy2(Path(__file__).with_name(f),r/'mppi'/f)
   shutil.copy2(Path(__file__).parents[1]/'nav2/floor.yaml',r/'nav2/floor.yaml')
   (r/'mppi/speed_profile.json').write_text(json.dumps(dict(name=name)))
   subprocess.run([sys.executable,str(r/'mppi/make_config.py')],check=True)
   return yaml.safe_load((r/'mppi/params.yaml').read_text())
 def test_profiles_match_across_layers(self):
  for name in PROFILES:
   p=self.config(name);q=from_config(p);self.assertEqual(q,profile(name))
   # Two-second MPPI horizon and full robot footprint must fit local map at 0.8.
   f=p['controller_server']['ros__parameters']['FollowPath'];self.assertLess(f['time_steps']*f['model_dt']*f['vx_max']+.5,p['local_costmap']['local_costmap']['ros__parameters']['width']/2)
 def test_mismatch_rejected(self):
  p=self.config('hall08');p['velocity_smoother']['ros__parameters']['max_velocity'][0]=.2
  with self.assertRaises(ValueError):from_config(p)
 def test_unsupported_limit_rejected(self):
  with self.assertRaises(ValueError):profile('fast')
  p=self.config('hall08');p['controller_server']['ros__parameters']['FollowPath']['vx_max']=2.
  with self.assertRaises(ValueError):from_config(p)
 def test_braking_horizon(self):
  for name in PROFILES:
   q=profile(name);age=source_age_limit(name);horizon=2.5 if name=='hall08' else 2.
   # Configured model only; actual braking distance still needs measurement.
   self.assertLess(q['vx_max']/q['decel']+age+.3,horizon)
 def test_source_age_contract_changes_only_corridor04(self):
  self.assertEqual(source_age_limit('corridor04'),.6)
  self.assertEqual(source_age_limit('baseline'),.5)
  self.assertEqual(source_age_limit('hall08'),.3)
  with self.assertRaises(ValueError):source_age_limit('unknown')
 def test_longer_sweep_rejects_farther_obstacle(self):
  import sys
  sys.path.insert(0,str(Path(__file__).parents[1]/'nav2'))
  from motion_policy import swept_clear
  data=[0]*14400;grid=(data,120,120,.05,-3.,-3.);data[60*120+107]=100
  swept_clear(grid,(0,0,0),(.8,0,0),horizon=2.)
  with self.assertRaises(ValueError):swept_clear(grid,(0,0,0),(.8,0,0),horizon=2.5)
if __name__=='__main__':unittest.main()
