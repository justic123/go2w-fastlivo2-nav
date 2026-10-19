#!/usr/bin/env python3
"""Bounded stationary sensor/estimator probe. Starts no navigation or command publishers."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--release',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--seconds',type=int,default=90)
p.add_argument('--image-profile',choices=['5hz','10hz'],default='5hz')
p.add_argument('--threads',type=int,choices=[1,2,4],default=2)
p.add_argument('--point-filter-num',type=int)
p.add_argument('--surface-leaf-size',type=float)
p.add_argument('--port',type=int,default=11641)
a=p.parse_args()
if not 15<=a.seconds<=180:raise SystemExit('Probe duration must be 15..180 seconds')
if a.point_filter_num is not None and a.point_filter_num<1:
    raise SystemExit('Point filter interval must be positive')
if a.surface_leaf_size is not None and not 0<a.surface_leaf_size<=1:
    raise SystemExit('Surface leaf size must be in (0, 1] meters')
base=Path('/home/unitree/fast_livo2_port/build1')
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():continue
    try:
        words=(entry/'cmdline').read_bytes().split(b'\0')
        if words and (Path(words[0].decode()).name in ('fastlivo_mapping','xt16_driver','unitree_slam') or
                      any(b'pipeline_runner.py' in word for word in words)):
            raise SystemExit('Conflicting live/replay process PID '+entry.name)
    except (OSError,UnicodeError):pass
with socket.socket() as sock:sock.bind(('127.0.0.1',a.port))
a.output.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,HOME='/home/unitree',OPENBLAS_NUM_THREADS='1',OMP_THREAD_LIMIT=str(a.threads),
         OMP_WAIT_POLICY='PASSIVE',GO2W_PROFILE='1',GO2W_CUDA_BACKEND='cpu',
         GO2W_IMAGE_PROFILE=a.image_profile)
raw=subprocess.check_output(['bash','-c','source "$1"; env -0','_',str(a.release/'ws/devel/setup.bash')],env=env)
env.update(dict(x.decode().split('=',1) for x in raw.split(b'\0') if b'=' in x))
env.update(ROS_MASTER_URI='http://127.0.0.1:'+str(a.port),ROS_IP='127.0.0.1',
           ROS_HOSTNAME='localhost',ROS_LOG_DIR=str(a.output/'ros_logs'))
children=[];handles=[];failure=None;ready=False;samples=[];fresh_since=None;initial_position=None
def start(role,command):
    log=(a.output/(role+'.log')).open('w');handles.append(log)
    child=subprocess.Popen(command,env=env,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
    children.append((role,child));return child
def run(command):
    subprocess.run(command,env=env,check=True,timeout=8,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def tail_pose():
    path=a.output/'bridge/odometry.jsonl'
    if not path.exists():return None
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-4096));rows=stream.read().splitlines()
    if not rows:return None
    try:return json.loads(rows[-1])
    except ValueError:return None
def cancel(*_):raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
try:
    start('master',['roscore','-p',str(a.port)])
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        try:run(['rosparam','list']);break
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired):time.sleep(.2)
    else:raise RuntimeError('Probe master unavailable')
    for name,namespace in [('livo.yaml','/go2w_lio'),('camera.yaml','/go2w_lio/laserMapping')]:
        run(['rosparam','load',str(a.release/name),namespace])
    if a.point_filter_num is not None:
        run(['rosparam','set','/go2w_lio/preprocess/point_filter_num',str(a.point_filter_num)])
    if a.surface_leaf_size is not None:
        run(['rosparam','set','/go2w_lio/preprocess/filter_size_surf',str(a.surface_leaf_size)])
    with (a.output/'parameters.yaml').open('w') as params:
        subprocess.run(['rosparam','get','/go2w_lio'],env=env,check=True,stdout=params,timeout=8)
    start('observer',['/usr/bin/python3',str(a.release/'tools/profile_sub.py'),str(a.output/'observations.jsonl')])
    start('algorithm',[str(a.release/'ws/devel/lib/fast_livo/fastlivo_mapping'),'__ns:=/go2w_lio',
                       '/aft_mapped_to_init:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud',
                       '/path:=/go2w_lio/path','/mavros/vision_pose/pose:=/go2w_lio/unused_pose'])
    start('decode',['/usr/bin/python3',str(HERE/'replay_decode.py'),str(a.output/'images.json'),a.image_profile,'--source-rate-limited'])
    start('driver',['bash','/home/unitree/go2w_slam_setup/helpers/run_driver.sh'])
    start('jpeg',[str(base/'mapping/jpeg_build/livo_jpeg'),'_duration_sec:=0',
                  '_rate_hz:='+('5' if a.image_profile=='5hz' else '10')])
    bridge=start('bridge',['/usr/bin/python3',str(base/'mapping/mapping_bridge.py'),
                           '--imu-source','ros2','--diagnostic','--point-time-unit','ns',
                           '--header-reference','end','--seconds',str(a.seconds),
                           '--max-radius','95','--output',str(a.output/'bridge')])
    begin=time.monotonic()
    print(json.dumps(dict(phase='initializing',output=str(a.output),image_profile=a.image_profile)),flush=True)
    while time.monotonic()-begin<a.seconds+35:
        if bridge.poll() is not None:
            if bridge.returncode:raise RuntimeError('Sensor bridge failed; inspect bridge.log')
            if not ready:raise RuntimeError('Sensor bridge ended without fresh odometry')
            break
        dead=[role for role,child in children if child.poll() is not None]
        if dead:raise RuntimeError('Probe child exited: '+','.join(dead))
        pose=tail_pose()
        if pose is not None:
            age=time.time()-pose['stamp']
            receipt_age=time.time()-pose['receipt']
            if 0<=receipt_age<1 and 0<=age<.4:
                if not ready:
                    if fresh_since is None:
                        fresh_since=time.monotonic();initial_position=pose['position']
                    if sum((x-y)**2 for x,y in zip(pose['position'],initial_position))>.15**2:
                        raise RuntimeError('Robot moved or initialization drifted more than 15cm')
                    if time.monotonic()-fresh_since>=4:
                        ready=True
                        print(json.dumps(dict(phase='ready',measurement_age_s=age,stable_seconds=4)),flush=True)
            elif not ready:
                fresh_since=None;initial_position=None
            sample=dict(wall_s=time.monotonic()-begin,measurement_age_s=age,
                        receipt_age_s=receipt_age,position=pose['position'])
            sample['temperatures_c']={}
            for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
                try:sample['temperatures_c'][(zone/'type').read_text().strip()]=int((zone/'temp').read_text())/1000
                except OSError:pass
            samples.append(sample)
        if not ready and time.monotonic()-begin>25:
            raise RuntimeError('No fresh sensor/estimator output within 25 seconds')
        time.sleep(.5)
    else:raise RuntimeError('Probe exceeded bounded deadline')
except BaseException as error:
    failure=type(error).__name__+': '+str(error)
finally:
    for role,child in sorted(children,key=lambda item: ['bridge','jpeg','decode','driver','algorithm','observer','master'].index(item[0])):
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGINT if role=='observer' else signal.SIGTERM)
            try:child.wait(timeout=12 if role=='bridge' else 5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    for handle in handles:handle.close()
    result=dict(release=str(a.release),seconds=a.seconds,image_profile=a.image_profile,threads=a.threads,
                point_filter_num=a.point_filter_num,surface_leaf_size=a.surface_leaf_size,
                ready=ready,error=failure,samples=samples)
    (a.output/'live_run.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(phase='finished',ready=ready,error=failure,samples=len(samples))),flush=True)
if failure:raise SystemExit(failure)
