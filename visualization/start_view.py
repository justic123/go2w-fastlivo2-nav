#!/usr/bin/env python3
"""Start the display in background; a start command is not a GUI wait loop."""
import fcntl,json,os,subprocess,time,re,shutil,signal
from pathlib import Path
root=Path(__file__).resolve().parents[1];cache=Path.home()/'.cache/go2w';cache.mkdir(parents=True,exist_ok=True)
state=cache/'viewer.json';log=cache/'viewer.log'
def birth(pid):
 try:
  f=Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split();return None if f[0]=='Z' else f[19]
 except FileNotFoundError:return None
def receivers():
 count=0
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   if d.stat().st_uid!=os.getuid():continue
   args=(d/'cmdline').read_bytes().decode().split('\0')
   if args and Path(args[0]).name.startswith('python') and any(a.endswith(('visualization/ros2_view.py','navigation/nav2/local_view.py')) for a in args[1:]):count+=1
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return count
def rviz_pids():
 result=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   if d.stat().st_uid!=os.getuid():continue
   args=(d/'cmdline').read_bytes().decode().split('\0')
   if Path(args[0]).name=='rviz2' and '-d' in args and Path(args[args.index('-d')+1]).resolve()==(root/'visualization/go2w_live_map.rviz').resolve():result.append(int(d.name))
  except (OSError,ValueError,IndexError):pass
 return result
def window_ready():
 if not shutil.which('xprop'):return bool(rviz_pids())
 try:
  clients=subprocess.check_output(['xprop','-root','_NET_CLIENT_LIST'],stderr=subprocess.DEVNULL,text=True,timeout=2)
  wanted=set(rviz_pids())
  for wid in re.findall(r'0x[0-9a-fA-F]+',clients):
   prop=subprocess.check_output(['xprop','-id',wid,'_NET_WM_PID'],stderr=subprocess.DEVNULL,text=True,timeout=1)
   match=re.search(r'= (\d+)',prop)
   if match and int(match.group(1)) in wanted:return True
  return False
 except (OSError,subprocess.SubprocessError):return False
with (cache/'viewer-control.lock').open('a') as lock:
 end=time.monotonic()+3
 while True:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:
   if time.monotonic()>end:raise SystemExit('显示启动正在进行，请稍后重试')
   time.sleep(.05)
 old=json.loads(state.read_text()) if state.exists() else {}
 if old.get('birth') and birth(old['pid'])==old['birth'] and receivers()==2 and window_ready():print('显示已运行，复用现有进程。');raise SystemExit(0)
 if old.get('birth') and birth(old['pid'])==old['birth']:
  subprocess.run(['bash',str(root/'关闭本机显示接收.sh')],timeout=8,check=True)
 # A matching RViz process without a managed window cannot be reused.
 if not window_ready():
  for pid in rviz_pids():
   identity=birth(pid)
   try:os.kill(pid,signal.SIGTERM)
   except ProcessLookupError:continue
   deadline=time.monotonic()+3
   while birth(pid)==identity and time.monotonic()<deadline:time.sleep(.1)
   if birth(pid)==identity:
    try:os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
 with log.open('a') as f:
  p=subprocess.Popen(['bash',str(root/'打开实时可视化.sh')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True,close_fds=True)
 state.write_text(json.dumps(dict(pid=p.pid,birth=birth(p.pid),root=str(root),log=str(log))))
 end=time.monotonic()+15
 while time.monotonic()<end:
  if p.poll() is not None:raise SystemExit('显示启动失败，查看 '+str(log))
  if receivers()==2 and window_ready():print('显示已在后台启动；本命令已完成。日志：'+str(log));raise SystemExit(0)
  time.sleep(.1)
 raise SystemExit('显示接收未就绪，查看 '+str(log))
