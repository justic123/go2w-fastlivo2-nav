"""One local action, one board guard; no robot SDK is loaded on the desktop."""
import socket,sys,json,os,signal
from pathlib import Path
from guard_client import Guard
root=Path(__file__).resolve().parent;state=Path(json.loads((root/'current.json').read_text())['folder']);path=state/'guard.sock';execute='--execute' in sys.argv;g=None
if path.exists():raise SystemExit('Guard socket already exists; inspect existing owner')
os.chdir(state)
s=socket.socket(socket.AF_UNIX);s.bind('guard.sock');os.chmod(path,0o600);s.listen(1);s.settimeout(25)
def interrupted(*_):raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
try:
 c,_=s.accept();c.settimeout(4)
 with c,c.makefile('rw') as f:
  for line in f:
   try:
    d=json.loads(line)
    if d['op']=='start' and g is None:
     if d['execute']!=execute:raise ValueError('Motion mode mismatch')
     g=Guard(execute);r=dict(ready=True,execute=execute)
    elif d['op']=='command' and g:
     g.send(d['v'],d['created']);r=dict(ok=True)
    elif d['op']=='stop' and g:
     r=dict(stop=g.close());g=None;f.write(json.dumps(r)+'\n');f.flush();break
    else:raise ValueError('Invalid guard protocol')
    f.write(json.dumps(r)+'\n');f.flush()
   except Exception as e:
    stop=None
    if g:
     try:stop=g.close()
     except Exception:pass
     g=None
    f.write(json.dumps(dict(error=str(e),stop=stop))+'\n');f.flush();break
finally:
 if g:g.close()
 s.close();path.unlink(missing_ok=True)
