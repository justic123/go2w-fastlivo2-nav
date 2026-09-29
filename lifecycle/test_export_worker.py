"""Real-process regression: terminating a paused export leaves no owned child."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from service_core import birth,owned_alive
class ExportTermination(unittest.TestCase):
 def test_paused_worker_term_and_int(self):
  for sig in (signal.SIGTERM,signal.SIGINT):
   with self.subTest(signal=sig),tempfile.TemporaryDirectory() as td:
    root=Path(td);run=root/'run';run.mkdir();(run/'sensors.bag').touch()
    (root/'continuous_capture.json').write_text(json.dumps(dict(pid=os.getpid(),birth=birth(os.getpid()))))
    (root/'compute_location.json').write_text('{"mode":"board"}')
    (root/'check_imu_continuity.py').write_text('import time\ntime.sleep(60)\n')
    env=dict(os.environ,GO2W_SERVICE_ROOT=td)
    p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('export_worker.py')),'run'],env=env)
    child=None
    try:
     end=time.monotonic()+5
     while time.monotonic()<end:
      try:state=json.loads((run/'export_status.json').read_text())
      except (OSError,ValueError):state={}
      if state.get('phase')=='paused_for_mapping':child=state['child'];break
      time.sleep(.05)
     self.assertIsNotNone(child)
     self.assertEqual(Path('/proc/%d/stat'%child['pid']).read_text().rsplit(')',1)[1].split()[0],'T')
     p.send_signal(sig);self.assertEqual(p.wait(timeout=6),128+sig)
     self.assertFalse(owned_alive(child))
     final=json.loads((run/'export_status.json').read_text());self.assertEqual(final['phase'],'failed');self.assertIn('interrupted',final['error'])
    finally:
     if p.poll() is None:p.kill();p.wait()
     if child and owned_alive(child):os.killpg(child['pid'],signal.SIGKILL)
if __name__=='__main__':unittest.main()
