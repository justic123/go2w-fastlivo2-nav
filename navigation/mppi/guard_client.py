"""SSH transport for the independent board guard; default is non-actuating preview."""
import subprocess,json,time,threading,queue,math
class Guard:
 def __init__(self,execute=False):
  self.rows=[];self.q=queue.Queue();self.offset=None;self.clock_checks=[];self.calibrated_at=0.
  self.p=subprocess.Popen(['ssh','-S','/home/river/.ssh/go2w-mapping.sock','-o','BatchMode=yes','-o','ConnectTimeout=4','unitree@192.168.123.18','python3','/home/unitree/fast_livo2_port/build1/navigation/mppi_guard/relay.py','execute' if execute else 'preview'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
  def read():
   for line in self.p.stdout:
    try:d=json.loads(line)
    except ValueError:continue
    self.rows.append(d);self.q.put(d)
  self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
  try:
   self.calibrate(5)
   self.write(dict(op='start'));d=self.q.get(timeout=3)
   if not d.get('ready'):raise RuntimeError('Board guard not ready')
  except Exception:
   self.close();raise
 def calibrate(self,count=3):
  candidates=[]
  for _ in range(count):
   token=time.monotonic_ns();sent=time.monotonic();self.write(dict(op='clock',token=token));d=self.q.get(timeout=3 if self.offset is None else .2);received=time.monotonic()
   if d.get('token')!=token:raise RuntimeError('Clock handshake mismatch: '+str(d))
   candidates.append((received-sent,d['remote_monotonic']-received))
  rtt,lower=min(candidates)
  if rtt>.05:raise RuntimeError('SSH timing uncertainty exceeds 50 ms')
  # Refresh while idle between command acknowledgments. A 3 ms margin makes
  # translated stamps older, never grants extra command lifetime.
  old=self.offset;self.rtt=rtt;self.offset=lower-.003;self.calibrated_at=time.monotonic()
  self.clock_checks.append(dict(t=self.calibrated_at,rtt_s=rtt,offset=self.offset,change_s=None if old is None else self.offset-old))
 def write(self,d):
  if self.p.poll() is not None:raise RuntimeError('Board guard exited')
  self.p.stdin.write(json.dumps(d)+'\n');self.p.stdin.flush()
 def send(self,v,created=None):
  if len(v)!=3 or not all(math.isfinite(x) for x in v) or not -.1<=v[0]<=.2 or abs(v[1])>1e-8 or abs(v[2])>.8:raise ValueError('Command outside MPPI limits')
  created=time.monotonic() if created is None else created
  if time.monotonic()-self.calibrated_at>=2.:self.calibrate()
  self.write(dict(vx=v[0],vy=0.,yaw_rate=v[2],sent_monotonic=created+self.offset))
  d=self.q.get(timeout=.25)
  if d.get('code')!=0:raise RuntimeError('Guard refused command: '+str(d))
 def close(self):
  if self.p.stdin and not self.p.stdin.closed:self.p.stdin.close()
  try:self.p.wait(timeout=4)
  except subprocess.TimeoutExpired:self.p.terminate();self.p.wait(timeout=3)
  self.reader.join(timeout=1)
  result=next((d for d in reversed(self.rows) if 'stop_code' in d),None)
  if result is not None:result=dict(result,clock_checks=self.clock_checks)
  return result
