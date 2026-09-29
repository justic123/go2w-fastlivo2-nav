"""Same-host UNIX transport; preserve the command's first guard-callback monotonic receipt time."""
import os,socket,json
class GuardError(RuntimeError):
 def __init__(self,message,stop=None):super().__init__(message);self.stop=stop
class Guard:
 def __init__(self,execute=False):
  self.s=socket.socket(socket.AF_UNIX);self.s.settimeout(3);self.s.connect(os.environ['GO2W_GUARD_SOCKET']);self.f=self.s.makefile('rw');self.request(dict(op='start',execute=execute));self.s.settimeout(.4)
 def request(self,d):
  self.f.write(json.dumps(d)+'\n');self.f.flush();line=self.f.readline()
  if not line:raise RuntimeError('Guard proxy disconnected')
  r=json.loads(line)
  if 'error' in r:raise GuardError(r['error'],r.get('stop'))
  return r
 def send(self,v,created=None):return self.request(dict(op='command',v=v,created=created))
 def close(self):
  try:return self.request(dict(op='stop')).get('stop')
  finally:self.f.close();self.s.close()
