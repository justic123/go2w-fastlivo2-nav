#!/usr/bin/env python3
"""Laptop lease sender; stdin EOF/link failure stops the board goal."""
import argparse,math,os,signal,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('mode',choices=['preview','execute']);p.add_argument('forward',type=float,nargs='?',default=.5);p.add_argument('left',type=float,nargs='?',default=0);p.add_argument('--floor',action='store_true');p.add_argument('--map-goal',action='store_true');p.add_argument('--yaw',type=float);p.add_argument('--named-goal');a=p.parse_args()
if not all(math.isfinite(v) for v in (a.forward,a.left)) or (not a.floor and not .1<=math.hypot(a.forward,a.left)<=2) or (a.floor and math.hypot(a.forward,a.left)>160):p.error('短距离0.1–2米；楼层相对位移最大160米')
if a.mode=='execute':
 print('真实路径跟踪：请停止遥控输入，保留紧急接管；5秒内Ctrl+C可取消。',flush=True)
 for i in range(5,0,-1):print(i,flush=True);time.sleep(1)
sock=str(Path.home()/'.ssh/go2w-mapping.sock');run='nav-goal-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid());root='/home/unitree/fast_livo2_port/build1'
# Arguments are fixed strings or validated finite numbers; no user shell text.
remote='source /opt/ros/foxy/setup.bash; export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1 OPENBLAS_NUM_THREADS=1; exec python3 '+root+'/navigation/nav2/navigate.py --forward '+str(a.forward)+' --left '+str(a.left)+' --output '+root+'/'+run+(' --execute' if a.mode=='execute' else '')
import shlex
if a.floor:remote+=' --floor'
if a.map_goal:remote+=' --map-goal'
if a.yaw is not None:
 if not math.isfinite(a.yaw):raise SystemExit('朝向必须为有限数值')
 remote+=' --yaw '+str(a.yaw)
if a.named_goal:remote+=' --named-goal '+shlex.quote(a.named_goal)
print('板端结果目录：'+root+'/'+run,flush=True)
proc=subprocess.Popen(['ssh','-S',sock,'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=1','-o','ServerAliveCountMax=2','unitree@192.168.123.18','bash -c '+shlex.quote(remote)],stdin=subprocess.PIPE,text=True)
stopped=False
def stop(*_):
 global stopped
 stopped=True
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
try:
 while proc.poll() is None and not stopped:
  proc.stdin.write('HEARTBEAT\n');proc.stdin.flush();time.sleep(.2)
except (BrokenPipeError,OSError):pass
finally:
 try:proc.stdin.close()
 except (BrokenPipeError,OSError):pass
 try:proc.wait(timeout=6)
 except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
raise SystemExit(proc.returncode or (1 if stopped else 0))
