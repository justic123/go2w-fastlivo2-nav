#!/usr/bin/env python3
"""Switch floor/short profiles only while navigation and capture are stopped."""
import argparse,json,subprocess,os
from pathlib import Path
root=Path('/home/unitree/fast_livo2_port/build1');p=argparse.ArgumentParser();p.add_argument('mode',choices=['floor','short','status']);a=p.parse_args();path=root/'navigation_profile'
old=path.read_text().strip() if path.exists() else 'short'
if a.mode=='status':print(old);raise SystemExit(0)
if a.mode==old:print('profile unchanged: '+old);raise SystemExit(0)
for command in [root/'capture_control.py',root/'navigation/nav2/control.py',root/'navigation/nav2/goal_control.py']:
 s=json.loads(subprocess.check_output(['python3',str(command),'status']))
 if s.get('running'):raise SystemExit('先正常停止目标、导航和采集再切换模式：'+str(command))
tmp=path.with_suffix('.tmp');tmp.write_text(a.mode+'\n');os.replace(str(tmp),str(path));print('profile: '+old+' -> '+a.mode)
