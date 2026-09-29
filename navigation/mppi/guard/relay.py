"""Exclusive board motion lease. Clock handshake never rewrites incoming command ages."""
import sys,json,time,fcntl,subprocess,threading,signal
from pathlib import Path
root=Path('/home/unitree/fast_livo2_port/build1');child=None;reader=None
# Preview never creates DDS participants. Execute must be explicit.
mode=sys.argv[1] if len(sys.argv)>1 else 'preview'
if mode not in ('preview','execute'):raise SystemExit('preview/execute')
lock=(root/'point_trial.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Another navigation/motion owner holds point_trial.lock')
def terminate(*args):
 if child and child.poll() is None:child.terminate()
 raise SystemExit('relay interrupted')
signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
def output():
 for line in child.stdout:sys.stdout.write(line);sys.stdout.flush()
try:
 for line in sys.stdin:
  obj=json.loads(line)
  if obj.get('op')=='clock':
   print(json.dumps(dict(op='clock',token=obj['token'],remote_monotonic=time.monotonic())),flush=True)
  elif obj.get('op')=='start' and child is None:
   deadline=obj.get('deadline_s',125)
   if type(deadline) is not int or not 5<=deadline<=1800:raise ValueError('Invalid guard deadline')
   child=subprocess.Popen([str(root/'navigation/mppi_guard/build/mppi_guard'),'eth0','--'+mode+'-mppi',str(deadline)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
   reader=threading.Thread(target=output,daemon=True);reader.start()
  elif child is not None:
   # Preserve sent_monotonic exactly; C++ independently rejects late packets.
   child.stdin.write(line);child.stdin.flush()
  else:raise ValueError('Expected clock or start')
finally:
 if child:
  if child.stdin and not child.stdin.closed:child.stdin.close()
  try:child.wait(timeout=2)
  except subprocess.TimeoutExpired:
   child.terminate();child.wait(timeout=2)
  if reader:reader.join(timeout=1)
