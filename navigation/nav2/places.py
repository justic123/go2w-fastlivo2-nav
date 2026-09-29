#!/usr/bin/env python3
"""Record named map poses, bound to the current SLAM session."""
import argparse,fcntl,json,math,os,re,time
from pathlib import Path
from mapping_session import current_mapping_run
p=argparse.ArgumentParser();p.add_argument('action',choices=['record','list']);p.add_argument('name',nargs='?');a=p.parse_args()
root=Path('/home/unitree/fast_livo2_port/build1');state=root/'navigation_places.json'
run=current_mapping_run(root)
with (root/'navigation_places.lock').open('w') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 d=json.loads(state.read_text()) if state.exists() else dict(mapping_run=run,places={})
 if a.action=='list':print(json.dumps(dict(current_mapping_run=run,stored=d),ensure_ascii=False,indent=2));raise SystemExit(0)
 if not a.name or not re.fullmatch(r'[\w\-]{1,40}',a.name):raise SystemExit('地点名称仅限文字/数字/下划线/短横线，最多40字')
 snap=json.loads(Path('/dev/shm/go2w_nav/pose.json').read_text());v=snap['pose'];now=time.time()
 if not all(math.isfinite(x) for x in v) or not 0<=now-snap['receipt']<.85 or not 0<=now-snap['stamp']<.85:raise SystemExit('位姿数据过期，拒绝记录')
 x,y,z,w=v[3:];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
 if d['mapping_run']!=run:
  state.rename(root/('navigation_places-'+d['mapping_run']+'.json'));d=dict(mapping_run=run,places={})
 d['places'][a.name]=dict(pose=[v[0],v[1],yaw],stamp=snap['stamp'],saved_at=now)
 tmp=state.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2));tmp.replace(state)
 print(json.dumps(dict(name=a.name,mapping_run=run,point=d['places'][a.name]),ensure_ascii=False))
