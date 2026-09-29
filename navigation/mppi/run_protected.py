"""Run the ROS action inside its matching Humble container; SSH stays on the host."""
import subprocess,sys,time,json,fcntl
from pathlib import Path
root=Path(__file__).resolve().parent;mode='--execute' if '--execute' in sys.argv else '--preview';state=Path(json.loads((root/'current.json').read_text())['folder'])
lock=(root/'action.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
subprocess.run(['docker','exec','go2w-nav2-mppi','mkdir','-p','/tmp/mppi_policy'],check=True)
for name in ('motion_policy.py','heading_guard.py'):
 subprocess.run(['docker','cp',str(root.parent/'nav2'/name),'go2w-nav2-mppi:/tmp/mppi_policy/'+name],check=True)
p=subprocess.Popen(['/usr/bin/python3',str(root/'guard_server.py'),mode])
try:
 end=time.monotonic()+3
 while not (state/'guard.sock').exists():
  if p.poll() is not None or time.monotonic()>end:raise RuntimeError('Guard proxy startup failed')
  time.sleep(.03)
 r=subprocess.run(['docker','exec','-e','GO2W_GUARD_SOCKET=/state/guard.sock','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/execute.py "$@"','_',mode])
finally:
 subprocess.run(['docker','exec','go2w-nav2-mppi','pkill','-INT','-f','^python3 /work/execute.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
raise SystemExit(r.returncode)
