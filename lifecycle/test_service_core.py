import unittest,tempfile,subprocess,os,json,time,signal,fcntl
from pathlib import Path
MODULE=Path(__file__).resolve().parent
FAKE=r'''
import signal,sys,time,subprocess,os
from pathlib import Path
from service_core import ROOT,atomic,birth
service,run=sys.argv[1:];r=ROOT/run;stop=False
p=subprocess.Popen(['sleep','300'],start_new_session=True,close_fds=True)
child=dict(pid=p.pid,birth=birth(p.pid),role='worker')
atomic(r/'runtime.json',dict(phase='starting',children=[child]))
def sig(*a):
 global stop
 stop=True
signal.signal(signal.SIGTERM,sig)
time.sleep(.3)
atomic(r/'runtime.json',dict(phase='running',children=[child]))
while not stop:time.sleep(.02)
atomic(r/'runtime.json',dict(phase='stopping',children=[child]));time.sleep(.3)
os.killpg(p.pid,signal.SIGTERM);p.wait()
e=subprocess.Popen(['sleep','4'],start_new_session=True,close_fds=True)
atomic(r/'export_status.json',dict(phase='queued',pid=e.pid))
atomic(r/'runtime.json',dict(phase='stopped',children=[child]))
'''
class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.runner=self.root/'fake.py';self.runner.write_text(FAKE)
  self.env=dict(os.environ,GO2W_SERVICE_ROOT=str(self.root),GO2W_SERVICE_RUNNER=str(self.runner),PYTHONPATH=str(MODULE))
 def proc(self,action,run='test'):
  return subprocess.Popen(['/usr/bin/python3','-c',"from service_core import main;main('capture')",action,run],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def call(self,action,run='test'):
  p=self.proc(action,run);out,err=p.communicate(timeout=8);self.assertEqual(p.returncode,0,(out,err));return json.loads(out)
 def tearDown(self):
  try:self.call('stop')
  except Exception:pass
  for p in self.root.glob('*/export_status.json'):
   try:os.kill(json.loads(p.read_text())['pid'],signal.SIGTERM)
   except (OSError,KeyError):pass
  self.tmp.cleanup()
 def test_concurrent_start_single_owner(self):
  a=self.proc('start','a');b=self.proc('start','b');x=json.loads(a.communicate(timeout=8)[0]);y=json.loads(b.communicate(timeout=8)[0]);self.assertEqual(x['pid'],y['pid']);self.assertTrue(x['ready'] and y['ready']);self.assertEqual(len(list(self.root.glob('*/runtime.json'))),1)
 def test_status_ignores_control_lock(self):
  with (self.root/'capture_control_v2.lock').open('w') as f:
   fcntl.flock(f,fcntl.LOCK_EX);t=time.monotonic();s=self.call('status');self.assertLess(time.monotonic()-t,1);self.assertFalse(s['running'])
 def test_stop_idempotent_and_exports_do_not_block_start(self):
  first=self.call('start','first');a=self.proc('stop');b=self.proc('stop');x=json.loads(a.communicate(timeout=8)[0]);y=json.loads(b.communicate(timeout=8)[0]);self.assertFalse(x['running'] or y['running']);self.assertEqual(self.call('stop')['children_alive'],0)
  e=json.loads((self.root/'first/export_status.json').read_text());os.kill(e['pid'],0)
  second=self.call('start','second');self.assertNotEqual(first['pid'],second['pid']);self.assertTrue(second['ready'])
 def test_foreign_process_not_stopped(self):
  p=subprocess.Popen(['sleep','30'],start_new_session=True)
  try:self.call('start');self.call('stop');self.assertIsNone(p.poll())
  finally:p.terminate();p.wait()
 def test_locks_not_inherited(self):
  s=self.call('start');child=json.loads((self.root/s['run']/'runtime.json').read_text())['children'][0]
  targets=[]
  for fd in Path('/proc/%d/fd'%child['pid']).iterdir():
   try:targets.append(os.readlink(fd))
   except OSError:pass
  self.assertFalse(any('control_v2.lock' in x for x in targets),targets)
if __name__=='__main__':unittest.main()
