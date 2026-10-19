import importlib.util,json,subprocess,tempfile,unittest,fcntl
from pathlib import Path
from unittest.mock import Mock,patch
import select_speed as speed
class SpeedSelection(unittest.TestCase):
 def test_daemon_or_inspect_failure_is_not_stopped(self):
  for outputs in ([Mock(returncode=1,stderr='permission denied')],[Mock(returncode=0,stdout='id'),Mock(returncode=1,stderr='lost')],[Mock(returncode=0,stdout='id'),Mock(returncode=0,stdout='true')]):
   with self.assertRaises(RuntimeError):speed.ensure_stopped(Mock(side_effect=outputs))
 def test_absent_or_stopped_is_allowed(self):
  speed.ensure_stopped(Mock(return_value=Mock(returncode=0,stdout='')))
  speed.ensure_stopped(Mock(side_effect=[Mock(returncode=0,stdout='id'),Mock(returncode=0,stdout='false')]))
 def test_generation_failure_rolls_back_all_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);m=root/'navigation/mppi';m.mkdir(parents=True);(root/'demo').mkdir()
   p=m/'speed_profile.json';p.write_text('{"name":"baseline"}')
   config=m/'params.yaml';config.write_text('baseline')
   with patch.object(speed,'ensure_stopped'),patch.object(speed.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'generate')):
    with self.assertRaises(subprocess.CalledProcessError):speed.select('corridor04',root)
   self.assertEqual(json.loads(p.read_text())['name'],'baseline');self.assertEqual(config.read_text(),'baseline');self.assertFalse((m/'demo_nav.yaml').exists())
 def test_motion_or_control_lock_prevents_config_mutation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);m=root/'navigation/mppi';m.mkdir(parents=True);(root/'demo').mkdir();p=m/'speed_profile.json';p.write_text('{"name":"baseline"}')
   with (m/'control.lock').open('a') as lock,patch.object(speed,'ensure_stopped') as check:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaises(RuntimeError):speed.select('corridor04',root)
    check.assert_not_called()
   (m/'current.json').write_text(json.dumps({'folder':str(tmp)}));(root/'motion_active').touch()
   with patch.object(speed,'ensure_stopped'):
    with self.assertRaises(RuntimeError):speed.select('corridor04',root)
   self.assertEqual(json.loads(p.read_text())['name'],'baseline')
if __name__=='__main__':unittest.main()
