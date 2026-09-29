#!/usr/bin/env bash
# 只停止当前登录用户的两个显示接收程序。不停止板端建图/导航/运控，不关闭SSH。
set -euo pipefail
/usr/bin/python3 - <<'PY'
import os,signal,time
from pathlib import Path
suffixes=('desktop/ros2_view.py','visualization/ros2_view.py','navigation/nav2/local_view.py')
stopping=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if p.stat().st_uid!=os.getuid():continue
  args=(p/'cmdline').read_bytes().decode().split('\0')
  receiver=args and Path(args[0]).name.startswith('python') and any(a.endswith(suffixes) for a in args[1:])
  supervisor=args and Path(args[0]).name in ('bash','sh') and '--clean' in args and any(Path(a).name=='打开实时可视化.sh' for a in args[1:])
  if receiver or supervisor:
   stopping.append((p,(p/'stat').read_text().rsplit(')',1)[1].split()[19]));print('停止本机显示接收进程',p.name);os.kill(int(p.name),signal.SIGTERM)
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
# Wait for exit before a new viewer's duplicate check; otherwise restart can skip both receivers.
end=time.monotonic()+3
while stopping:
 remaining=[]
 for p,birth in stopping:
  try:
   stat=(p/'stat').read_text().rsplit(')',1)[1].split()
   if stat[0]!='Z' and stat[19]==birth:remaining.append((p,birth))
  except FileNotFoundError:pass
 if not remaining:break
 if time.monotonic()>end:
  for p,birth in remaining:
   try:os.kill(int(p.name),signal.SIGKILL)
   except ProcessLookupError:pass
  time.sleep(.1);break
 stopping=remaining;time.sleep(.05)
print('显示接收已停止。板端任务未改动；再次启动可复用已有RViz窗口。')
PY
