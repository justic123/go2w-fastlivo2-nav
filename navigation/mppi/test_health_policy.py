import json,tempfile,unittest
from pathlib import Path
from health_policy import check_context,ContextError
from speed_profiles import source_age_limit
class ContextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.target=dict(map_id='m',source_session='s')
  self.docs=dict(input=dict(ready=True,updated=100,session='s',pose_age_s=.2,cloud_age_s=.4),localization=dict(ready=True,updated=100,map_id='m',source_session='s'),lifecycle=dict(ready=True,updated=100),runtime=dict(phase='running',updated=100))
 def tearDown(self):self.tmp.cleanup()
 def check(self,max_age=None):
  if max_age is None:max_age=source_age_limit('corridor04')
  for k,v in self.docs.items():(self.root/(k+'.json')).write_text(json.dumps(v))
  return check_context(self.root,self.target,max_age,100)
 def test_failed_age_retains_exact_pre_stop_data(self):
  self.docs['input']['cloud_age_s']=.604725933
  self.docs['input']['cloud_diagnostics']={'wait_s':.2}
  with self.assertRaises(ContextError) as caught:self.check()
  snapshot=caught.exception.snapshot
  self.assertEqual(snapshot['captured'],100)
  self.assertEqual(snapshot['documents']['input']['cloud_age_s'],.604725933)
  self.assertEqual(snapshot['documents']['input']['cloud_diagnostics']['wait_s'],.2)
 def test_valid_current_context_and_stricter_hall_limit(self):
  self.check()
  with self.assertRaises(RuntimeError):self.check(.3)
 def test_corridor_accepts_raised_window_and_rejects_excess_for_both_sources(self):
  for key in ('pose_age_s','cloud_age_s'):
   for age in (.5,.55,.6):
    self.docs['input'][key]=age
    with self.subTest(key=key,age=age):self.check()
   self.docs['input'][key]=.600001
   with self.subTest(key=key),self.assertRaises(ContextError):self.check()
   self.docs['input'][key]=.2
 def test_future_stale_and_nan_health_rejected(self):
  for t in (101,98,float('nan')):
   self.docs['input']['updated']=t
   with self.subTest(t=t),self.assertRaises(RuntimeError):self.check()
 def test_localizer_from_different_session_rejected(self):
  self.docs['localization']['source_session']='old'
  with self.assertRaisesRegex(RuntimeError,'会话'):self.check()
 def test_degraded_runtime_blocks_even_with_fresh_valid_pose(self):
  self.docs['runtime']['phase']='degraded'
  with self.assertRaisesRegex(RuntimeError,'runtime未就绪'):self.check()
 def test_nonfinite_and_negative_source_age_rejected(self):
  for age in (float('nan'),float('inf'),-.1):
   self.docs['input']['pose_age_s']=age
   with self.subTest(age=age),self.assertRaises(RuntimeError):self.check()
if __name__=='__main__':unittest.main()
