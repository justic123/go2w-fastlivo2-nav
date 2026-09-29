#!/usr/bin/env python3
"""Signal only the verified goal process. SIGTERM closes the motion pipe first."""
import json,sys,os,signal
from pathlib import Path
p=Path('/home/unitree/fast_livo2_port/build1/navigation_goal.json')
s=json.loads(p.read_text()) if p.exists() else {'running':False}
try:
 stat=Path('/proc/%d/stat'%s['pid']).read_text().rsplit(')',1)[1].split()
 s['running']=s.get('running',False) and stat[0]!='Z' and stat[19]==s['birth']
except (FileNotFoundError,KeyError):s['running']=False
if sys.argv[1]=='stop' and s['running']:os.kill(s['pid'],signal.SIGTERM);s['stop_requested']=True
elif sys.argv[1] not in ('status','stop'):raise SystemExit('status/stop only')
print(json.dumps(s))
