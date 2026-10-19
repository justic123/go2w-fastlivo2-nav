import hashlib,json,queue,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from go2w_mode_adapter import Go2WModeAdapter
class HardwareBoundary(unittest.TestCase):
 def test_flat_container_import_does_not_initialize_hardware(self):
  source=Path(__file__).with_name('go2w_mode_adapter.py').read_text()
  namespace={'__file__':'/work/go2w_mode_adapter.py','__name__':'container_adapter'}
  exec(compile(source,namespace['__file__'],'exec'),namespace)
  self.assertIsNone(namespace['ROOT'])
  with self.assertRaisesRegex(RuntimeError,'宿主机'):namespace['Go2WModeAdapter']()
 def test_capability_requires_machine_binary_and_distinct_feedback(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);(r/'board/calibration').mkdir(parents=True);(r/'navigation/mppi/guard/build').mkdir(parents=True)
   (r/'board/deployment.json').write_text('{"backend":"board"}')
   b=r/'navigation/mppi/guard/build/go2w_mode_bridge';b.write_bytes(b'fixture')
   c={'verified':True,'machine_id':Path('/etc/machine-id').read_text().strip(),'binary_sha256':hashlib.sha256(b.read_bytes()).hexdigest(),'api':'b2.SwitchGait','request':{'normal':0,'obstacle':1},'feedback_gait':{'normal':0,'obstacle':1}}
   f=r/'board/calibration/motion_modes.json';f.write_text(json.dumps(c));a=Go2WModeAdapter(r)
   self.assertEqual(a.supported_modes(),{'normal','obstacle'})
   b.write_bytes(b'changed');self.assertFalse(a.supported_modes());b.write_bytes(b'fixture')
   c['feedback_gait']['obstacle']=0;f.write_text(json.dumps(c));self.assertFalse(a.supported_modes())
   c['feedback_gait']['obstacle']=1;c['machine_id']='wrong';f.write_text(json.dumps(c));self.assertFalse(a.supported_modes())
 def test_stale_pre_request_future_unknown_feedback_never_confirms(self):
  a=Go2WModeAdapter();a.config={'feedback_gait':{'normal':0,'obstacle':1}};a.after=99.8
  with patch('go2w_mode_adapter.time.monotonic',return_value=100.):
   for stamp,gait in [(99.7,1),(101,1),(99.9,2)]:
    a.feedback_queue.put({'kind':'feedback','received_monotonic':stamp,'gait_type':gait});self.assertNotEqual(a.read_mode().get('mode'),'obstacle')
   a.feedback_queue.put({'kind':'feedback','received_monotonic':99.9,'gait_type':1});self.assertEqual(a.read_mode()['mode'],'obstacle')
 def test_fast_profile_rejected_for_obstacle(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);(r/'navigation/mppi').mkdir(parents=True)
   (r/'navigation/mppi/speed_profile.json').write_text('{"name":"hall08"}')
   a=Go2WModeAdapter(r)
   with self.assertRaisesRegex(RuntimeError,'0.8'):a.check_limits({'obstacle'})
   a.check_limits({'normal'})
 def test_unverified_never_spawns_robot_client(self):
  with tempfile.TemporaryDirectory() as t,patch('go2w_mode_adapter.subprocess.Popen') as p:
   with self.assertRaises(RuntimeError):Go2WModeAdapter(t).set_mode('obstacle',checkpoint={})
   p.assert_not_called()
if __name__=='__main__':unittest.main()
