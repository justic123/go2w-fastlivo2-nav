#!/usr/bin/env python3
"""Board-only isolated bag replay. No drivers, SDK, navigation, power or live-state writes."""
import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import time

p=argparse.ArgumentParser()
p.add_argument('--release', type=Path, required=True)
p.add_argument('--bag', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--seconds', type=float, default=120)
p.add_argument('--backend', choices=['cpu','shadow'], default='cpu')
p.add_argument('--port', type=int, default=11441)
p.add_argument('--image-profile', choices=['off','5hz','10hz'], default='10hz')
p.add_argument('--threads', type=int, choices=[1,2,4], default=2)
p.add_argument('--point-filter-num', type=int)
p.add_argument('--surface-leaf-size', type=float)
a=p.parse_args()
base=Path(os.environ.get('GO2W_BOARD_BASE','/home/unitree/fast_livo2_port/build1'))
if not a.bag.is_file() or not 0<a.seconds<=1800:
    raise SystemExit('Invalid bag or duration')
if a.point_filter_num is not None and a.point_filter_num < 1:
    raise SystemExit('Point filter interval must be positive')
if a.surface_leaf_size is not None and not 0 < a.surface_leaf_size <= 1:
    raise SystemExit('Surface leaf size must be in (0, 1] meters')
decoder=Path(__file__).resolve().with_name('replay_decode.py')
if a.image_profile != 'off' and not decoder.is_file():
    raise SystemExit('Copy replay_decode.py next to replay.py for measured image-rate control')
for proc in Path('/proc').iterdir():
    if proc.name.isdigit():
        try:
            cmd=(proc/'cmdline').read_bytes().split(b'\0')
            if cmd and (Path(cmd[0].decode()).name in ('fastlivo_mapping','xt16_driver') or
                        any(b'pipeline_runner.py' in x for x in cmd)):
                raise SystemExit('Stop active mapping/capture before replay; found PID '+proc.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
with socket.socket() as sock:
    sock.bind(('127.0.0.1',a.port))
a.output.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,HOME='/home/unitree',OPENBLAS_NUM_THREADS='1',OMP_THREAD_LIMIT=str(a.threads),OMP_WAIT_POLICY='PASSIVE',
         GO2W_PROFILE='1',GO2W_CUDA_BACKEND=a.backend,GO2W_IMAGE_PROFILE=a.image_profile)
setup=a.release/'ws/devel/setup.bash'
raw=subprocess.check_output(['bash','-c','source "$1"; env -0','_',str(setup)],env=env)
env.update(dict(x.decode().split('=',1) for x in raw.split(b'\0') if b'=' in x))
env.update(ROS_MASTER_URI='http://127.0.0.1:'+str(a.port),ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',ROS_LOG_DIR=str(a.output/'ros_logs'))
children=[];handles=[];samples=[];failure=None
begin=None;finished=None;latest_profile=None
def read_latest_profile():
    path=a.output/'observations.jsonl'
    if not path.exists():return None
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-32768))
        rows=stream.read().decode(errors='replace').splitlines()
    for row in reversed(rows):
        try:event=json.loads(row)
        except ValueError:continue
        if event.get('kind')=='profile':return event['data']
    return None
def start(role,cmd):
    f=(a.output/(role+'.log')).open('w');handles.append(f)
    proc=subprocess.Popen(cmd,env=env,stdout=f,stderr=f,stdin=subprocess.DEVNULL,start_new_session=True)
    children.append((role,proc));return proc
def run(cmd):
    subprocess.run(cmd,env=env,check=True,timeout=10,stdout=subprocess.DEVNULL)
def cancelled(*_):
    raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,cancelled)
signal.signal(signal.SIGINT,cancelled)
try:
    start('master',['roscore','-p',str(a.port)])
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        try:
            run(['rosparam','list']);break
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired):time.sleep(.2)
    else:raise RuntimeError('Replay master unavailable')
    run(['rosparam','set','/use_sim_time','true'])
    for name,ns in [('livo.yaml','/go2w_lio'),('camera.yaml','/go2w_lio/laserMapping')]:
        run(['rosparam','load',str(a.release/name),ns])
    run(['rosparam','set','/go2w_lio/common/img_en','0' if a.image_profile=='off' else '1'])
    if a.point_filter_num is not None:
        run(['rosparam','set','/go2w_lio/preprocess/point_filter_num',str(a.point_filter_num)])
    if a.surface_leaf_size is not None:
        run(['rosparam','set','/go2w_lio/preprocess/filter_size_surf',str(a.surface_leaf_size)])
    with (a.output/'parameters.yaml').open('w') as params:
        subprocess.run(['rosparam','get','/go2w_lio'],env=env,check=True,stdout=params,timeout=10)
    start('observer',['/usr/bin/python3',str(a.release/'tools/profile_sub.py'),str(a.output/'observations.jsonl')])
    if a.image_profile != 'off':
        start('decode',['/usr/bin/python3',str(decoder),str(a.output/'images.json'),a.image_profile])
    node=start('algorithm',[str(a.release/'ws/devel/lib/fast_livo/fastlivo_mapping'),'__ns:=/go2w_lio',
                            '/aft_mapped_to_init:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud'])
    time.sleep(2)
    topics=['/go2w_lio/points','/go2w_lio/imu']
    if a.image_profile != 'off': topics.append('/go2w_livo/jpeg')
    player=start('player',['rosbag','play','--clock','--duration='+str(a.seconds),'--delay=2',str(a.bag),
                           '--topics']+topics)
    begin=time.monotonic()
    while time.monotonic()-begin<a.seconds+40:
        dead=[role for role,proc in children if role!='player' and proc.poll() is not None]
        if dead:raise RuntimeError('Replay child exited: '+','.join(dead))
        if player.poll() is not None:
            if player.returncode:raise RuntimeError('Bag player failed')
            if finished is None:finished=time.monotonic()
            latest_profile=read_latest_profile()
            lag=(latest_profile or {}).get('metrics',{}).get('processing_lag_s')
            if time.monotonic()-finished>1 and lag is not None and lag<=.5:break
            if time.monotonic()-finished>20:
                raise RuntimeError('Replay still backlogged 20s after input ended; lag='+str(lag))
        stat=Path('/proc/%d/status'%node.pid).read_text()
        latest_profile=read_latest_profile()
        samples.append(dict(wall_s=time.monotonic()-begin,rss=next(x for x in stat.splitlines() if x.startswith('VmRSS:')),
                            processing_lag_s=(latest_profile or {}).get('metrics',{}).get('processing_lag_s'),
                            player_finished=finished is not None))
        time.sleep(.5)
    else:raise RuntimeError('Replay deadline exceeded')
except BaseException as ex:
    failure=type(ex).__name__+': '+str(ex)
finally:
    for role,proc in reversed(children):
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGINT if role in ('observer','player') else signal.SIGTERM)
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    for f in handles:f.close()
    for name in ('mat_pre.txt','mat_out.txt'):
        log=a.release/'ws/src/FAST-LIVO2/Log'/name
        if log.exists():shutil.copy2(log,a.output/name)
    (a.output/'run.json').write_text(json.dumps(dict(release=str(a.release),bag=str(a.bag),backend=a.backend,
        seconds=a.seconds,image_profile=a.image_profile,threads=a.threads,
        point_filter_num=a.point_filter_num,surface_leaf_size=a.surface_leaf_size,
        decoder=str(decoder) if a.image_profile!='off' else None,
        replay_wall_s=time.monotonic()-begin if begin is not None else None,
        final_profile=latest_profile,error=failure,samples=samples),indent=2))
if failure:raise SystemExit(failure)
print(a.output)
