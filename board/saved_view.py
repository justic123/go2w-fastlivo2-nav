#!/usr/bin/env python3
"""Keep saved maps viewable while Nav2 is stopped. No robot control interfaces."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1];board=root/'board';work=root/'navigation/mppi'
p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop']);p.add_argument('--map-id');a=p.parse_args()
if a.map_id:
    if Path(a.map_id).name!=a.map_id or a.map_id in ('.','..'):raise SystemExit('Invalid map id')
    for name in ('map.yaml','map.pgm','points.npy'):
        if not (work/'maps'/a.map_id/name).is_file():raise SystemExit('Incomplete map')
name='go2w-onboard-view';label='go2w.onboard.view'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
with (board/'saved_view.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    result=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
    d=json.loads(result.stdout)[0] if result.returncode==0 else None
    if d and d['Config'].get('Labels',{}).get(label)!='readonly':raise SystemExit('Visualization container ownership mismatch')
    digest=hashlib.sha256(b''.join(path.read_bytes() for path in (board/'view_server.py',board/'view_runtime.py',board/'view_transport.py',work/'initial_pose.py',work/'mission_view.py'))).hexdigest()
    identity=json.dumps(dict(map_id=a.map_id,code=digest,transport='host-ipc'),sort_keys=True)
    if a.action=='start' and d and d['State']['Running'] and d['Config'].get('Labels',{}).get('go2w.view.identity')==identity:
        print('板载只读显示服务已运行');raise SystemExit(0)
    if d:
        if d['State']['Running']:run(['docker','stop','-t','8',name],stdout=subprocess.DEVNULL)
        run(['docker','rm',name],stdout=subprocess.DEVNULL)
    if a.action=='start':
        state=board/'display';state.mkdir(exist_ok=True)
        run(['docker','run','-d','--init','--name',name,'--label',label+'=readonly','--label','go2w.view.identity='+identity,
             '--network','host','--ipc','host','--user',f'{os.getuid()}:{os.getgid()}',
             '-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=1',
             '-v',str(root)+':'+str(root)+':ro', # Saved display resolves current.json's host paths.
             '-v',str(board)+':/board:ro','-v',str(work)+':/work:ro','-v',str(state)+':/view-state',
             '--entrypoint','bash','go2w-nav2-mppi:humble','-c',
             'source /opt/ros/humble/setup.bash; exec python3 /board/view_runtime.py "$@"','_',a.map_id or ''])
    print('板载只读显示服务已'+('启动' if a.action=='start' else '停止'))
