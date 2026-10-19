#!/usr/bin/env python3
"""Own native acquisition and fusion; no SportClient and no automatic restart."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from initialization import StationaryInitialization
from runtime_profile import settings
from port_check import check_ports
from fusion_backend import plan

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / 'desktop'))
from backlog_policy import BacklogGuard

cfg = json.loads((ROOT / 'deployment.json').read_text())
profile = settings(cfg)
backend = plan(cfg)
base = Path(cfg['sensor_base'])
release = Path(cfg['fusion_release'])
folder = ROOT / 'runs' / sys.argv[1]
children = [];handles = [];stop = False;error = None;recording = dict(phase='pending')
locks = []


def request_stop(*_):
    global stop
    stop = True


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)


def read(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):return {}


def status(phase):
    d = dict(phase=phase, error=error, compute_location='board', updated=time.time(),
             profile=cfg['profile'], fusion_backend=backend['name'], vision_enabled=backend['vision'], recording=recording,
             children=[dict(role=k,pid=p.pid,running=p.poll() is None) for k,p in children])
    temp = folder / 'runtime.tmp';temp.write_text(json.dumps(d));temp.replace(folder / 'runtime.json')


def start(role, args):
    if stop:raise RuntimeError('Stop requested during initialization')
    log = (folder / (role + '.log')).open('w');handles.append(log)
    p = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    children.append((role,p));return p


def run(args):
    subprocess.run(args,env=env,timeout=8,check=True,stdout=subprocess.DEVNULL)


def check_children():
    dead = [k for k,p in children if k != 'bag' and p.poll() is not None]
    if dead:raise RuntimeError('Onboard child exited: ' + ','.join(dead))


def stop_child(role, seconds=4):
    for k,p in children:
        if k != role or p.poll() is not None:continue
        os.killpg(p.pid,signal.SIGINT if role == 'bag' else signal.SIGTERM)
        try:p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            if role == 'bag':
                status('closing_bag');p.wait() # Never forcibly kill a sealing recorder.
            else:os.killpg(p.pid,signal.SIGKILL);p.wait()


try:
    status('starting')
    for path in (ROOT / 'runtime.lock', base / 'capture_pipeline_v2.lock'):
        lock = path.open('a');locks.append(lock);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            words = (proc / 'cmdline').read_bytes().split(b'\0')
            if words and Path(words[0].decode()).name in ('fastlivo_mapping','fastlio_mapping','xt16_driver','unitree_slam'):
                raise RuntimeError('External sensor/fusion owner PID ' + proc.name)
        except (FileNotFoundError,ProcessLookupError,PermissionError,UnicodeError):pass
    check_ports((11331,11335,11339))
    if Path('/var/lib/nvpmodel/status').read_text().strip() != 'pmode:0000':
        raise RuntimeError('MAXN is required for this installed onboard profile')
    if shutil.disk_usage(folder).free < 5 * 1024**3:raise RuntimeError('Need 5 GiB free before starting')
    env = dict(os.environ,HOME='/home/unitree',PATH='/usr/bin:/bin',OPENBLAS_NUM_THREADS='1',
               GO2W_PROFILE='0',GO2W_CUDA_BACKEND='cpu',
               GO2W_MPPI_SESSION=folder.name,GO2W_SOURCE_PORT='11335')
    env.update(profile['env'])
    raw = subprocess.check_output(['bash','-c','source "$1"; env -0','_',str(release / 'ws/devel/setup.bash')],env=env)
    env.update(dict(v.decode().split('=',1) for v in raw.split(b'\0') if b'=' in v))
    env.update(ROS_MASTER_URI='http://127.0.0.1:11331',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',ROS_LOG_DIR=str(folder/'ros_logs'))
    start('master',['roscore','-p','11331'])
    end = time.monotonic()+15
    while time.monotonic()<end:
        if stop:raise RuntimeError('Stopped during startup')
        check_children()
        try:run(['rosparam','list']);break
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired):time.sleep(.2)
    else:raise RuntimeError('Native ROS master unavailable')
    run(['rosparam','set','/use_sim_time','false'])
    for name,ns in backend['parameters']:
        shutil.copy2(release / name,folder / name)
        run(['rosparam','load',str(folder / name),ns])
    start('clock',['/usr/bin/python3',str(ROOT/'clock_source.py')])
    start('algorithm',[str(release/backend['binary']),'__ns:=/go2w_lio']+backend['remaps'])
    if backend['vision']:
        start('decode',['/usr/bin/python3',str(ROOT/'replay_decode.py'),str(folder/'images.json'),profile['decoder_mode'],'--source-rate-limited'])
    start('monitor',['/usr/bin/python3',str(PROJECT/'desktop/monitor.py'),str(folder/'health.json')])
    start('view',['/usr/bin/python3',str(PROJECT/'desktop/ros1_view_source.py')])
    start('nav_export',['/usr/bin/python3',str(PROJECT/'navigation/mppi/source_ros1.py')])
    start('driver',['bash','/home/unitree/go2w_slam_setup/helpers/run_driver.sh'])
    if backend['vision']:
        start('jpeg',[str(base/'mapping/jpeg_build/livo_jpeg'),'_duration_sec:=0','_rate_hz:='+str(profile['image_hz'])])
    start('bridge',['/usr/bin/python3',str(base/'mapping/mapping_bridge.py'),'--imu-source','ros2',
                    '--diagnostic','--point-time-unit','ns','--header-reference','end','--seconds','0',
                    '--max-radius','95','--output',str(folder/'bridge')])
    if backend['recording_enabled']:
        topics=['/go2w_lio/points','/go2w_lio/imu','/go2w_lio/odometry','/go2w_lio/processing_lag']
        if backend['vision']:topics.append('/go2w_livo/jpeg')
        start('bag',['/opt/ros/noetic/lib/rosbag/record','--lz4','--buffsize','128','-O',str(folder/'sensors.bag')]+topics)
        recording['phase']='running'
    else:
        recording['phase']='disabled'
    status('initializing');end=time.monotonic()+30;initialization=StationaryInitialization()
    while time.monotonic()<end:
        if stop:raise RuntimeError('Stopped during stationary initialization')
        check_children();h=read(folder/'health.json')
        if initialization.observe(h,time.time(),time.monotonic()):break
        time.sleep(.2)
    else:raise RuntimeError('No four continuous seconds of fresh stationary fusion')
    guard=BacklogGuard(soft=1.,hard=3.,grace=5.)
    while not stop:
        check_children();h=read(folder/'health.json')
        if time.time()-h.get('updated',0)>2:raise RuntimeError('Fusion health monitor stale')
        if h.get('monitor_age_s') is not None and h['monitor_age_s']>2:raise RuntimeError('Fusion output stopped')
        if h.get('lag_last_s') is not None:guard.check(h['lag_last_s'],time.monotonic())
        for role,p in children:
            if role!='bag':continue
            if p.poll() is not None and recording['phase'] in ('running','stopping'):recording.update(phase='closed' if p.returncode==0 else 'failed',returncode=p.returncode)
            elif p.poll() is None and recording['phase']=='running' and shutil.disk_usage(folder).free<2*1024**3:
                recording['phase']='stopping';os.killpg(p.pid,signal.SIGINT)
        status('running');time.sleep(.2)
except BaseException as e:
    error=type(e).__name__+': '+str(e)
    print(error,flush=True)
finally:
    status('stopping')
    for role in ('bridge','jpeg','driver','decode','bag','algorithm','nav_export','view','monitor','clock','master'):
        stop_child(role,15 if role in ('bridge','bag') else 4)
    status('failed' if error else 'stopped')
    for log in handles:log.close()
    for lock in locks:lock.close()
if error:raise SystemExit(error)
