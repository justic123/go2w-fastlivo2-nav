#!/usr/bin/env python3
"""Own only web display processes. Never starts fusion, Nav2 or motion."""
import os,signal,subprocess,time
from pathlib import Path
from common import ROOT,STATE,read,atomic
from camera_policy import reconnect_needed
stop=False;children=[];camera_process=None;camera_session=None;camera_retry=0.;name='go2w-web-view'
def request(*_):
    global stop
    stop=True
signal.signal(signal.SIGINT,request);signal.signal(signal.SIGTERM,request)
def run(a,**kw):return subprocess.run(a,check=True,**kw)
try:
    STATE.mkdir(parents=True,exist_ok=True)
    p=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
    if p.returncode==0:
        import json
        d=json.loads(p.stdout)[0]
        if d['Config'].get('Labels',{}).get('go2w.web')!='readonly':raise RuntimeError('Container ownership mismatch')
        run(['docker','rm','-f',name],stdout=subprocess.DEVNULL)
    run(['docker','run','-d','--init','--name',name,'--label','go2w.web=readonly','--network','host','--ipc','host',
         '-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=1','-v',str(ROOT)+':/project:ro','-v',str(STATE)+':/project/board/web-state',
         '--entrypoint','bash','go2w-nav2-mppi:humble','-c','source /opt/ros/humble/setup.bash; exec python3 /project/board/web/bridge.py'])
    env=dict(os.environ,ROS_MASTER_URI='http://127.0.0.1:11331',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost')
    def start_camera():
        return subprocess.Popen(['bash','-c','source /opt/ros/noetic/setup.bash; exec /usr/bin/python3 "$1"','_',str(ROOT/'board/web/camera.py')],env=env)
    camera_process=start_camera();camera_session=read(ROOT/'board/current.json').get('run');camera_retry=time.monotonic()
    children.append(subprocess.Popen(['/usr/bin/python3',str(ROOT/'board/web/server.py')]))
    while not stop:
        if any(p.poll() is not None for p in children):raise RuntimeError('Web child exited')
        current=read(ROOT/'board/current.json');session=current.get('run')
        folder=Path(current.get('folder','/nonexistent'));health=read(folder/'health.json')
        alive=health.get('ready') and 0<=time.time()-health.get('updated',0)<2
        camera=read(STATE/'cache/camera.json')
        if reconnect_needed(session,camera_session,time.monotonic()-camera_retry,camera_process.poll() is not None,alive,time.time()-camera.get('updated',0)):
            if camera_process.poll() is None:
                camera_process.terminate()
                try:camera_process.wait(timeout=3)
                except subprocess.TimeoutExpired:camera_process.kill();camera_process.wait()
            atomic(STATE/'cache/camera.json',dict(updated=0,source='/go2w_livo/jpeg',phase='reconnecting',session=session))
            camera_process=start_camera();camera_session=session;camera_retry=time.monotonic()
            print('Camera subscriber reconnected for '+str(session),flush=True)
        time.sleep(1)
finally:
    if camera_process is not None:children.insert(0,camera_process)
    for p in reversed(children):
        if p.poll() is None:p.terminate()
    for p in reversed(children):
        try:p.wait(timeout=25)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    subprocess.run(['docker','stop','-t','3',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
