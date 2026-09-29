import sys,time,json,subprocess,concurrent.futures,os
from pathlib import Path
sys.path.insert(0,'/home/unitree/fast_livo2_port/build1/lifecycle')
from service_core import ROOT,read,snapshot,atomic
report=[]
def call(service,action,run=None):
 t=time.monotonic();path=ROOT/('capture_control.py' if service=='capture' else 'navigation/nav2/control.py')
 p=subprocess.run(['python3',str(path),action,run or ('lifecycle-verify-'+str(time.monotonic_ns()))],capture_output=True,text=True,timeout=42)
 try:s=json.loads(p.stdout)
 except Exception:s={'stdout':p.stdout,'stderr':p.stderr}
 row=dict(service=service,action=action,seconds=round(time.monotonic()-t,3),code=p.returncode,state=s);report.append(row);atomic(ROOT/'lifecycle_verification.json',report);print(json.dumps(row),flush=True)
 assert p.returncode==0,row
 return s
with concurrent.futures.ThreadPoolExecutor(3) as e:
 for service in ['capture','nav']:
  rows=list(e.map(lambda _:call(service,'start'),range(3)))
  assert len({s['pid'] for s in rows})==1
for cycle in range(2):
 assert snapshot('capture')['ready'],snapshot('capture')
 for service in ['nav','capture']:
  with concurrent.futures.ThreadPoolExecutor(2) as e:rows=list(e.map(lambda _:call(service,'stop'),range(2)))
  assert all(not r['running'] and r['children_alive']==0 for r in rows)
  call(service,'stop');call(service,'status')
 old=read(ROOT/'continuous_capture.json')['run']
 assert (ROOT/old/'sensors.bag').exists() and not (ROOT/old/'sensors.bag.active').exists()
 with concurrent.futures.ThreadPoolExecutor(2) as e:rows=list(e.map(lambda _:call('capture','start'),range(2)))
 assert rows[0]['pid']==rows[1]['pid']
 call('nav','start')
 time.sleep(12)
 assert snapshot('capture')['ready'],snapshot('capture')
print('ALL LIFECYCLE CHECKS PASSED',flush=True)
