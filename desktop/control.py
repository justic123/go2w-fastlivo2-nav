"""Desktop container lifecycle. This control never invokes robot actuation."""
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent;name='go2w-livo-desktop';state=root/'current.json'
def inspect():
 p=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
 if p.returncode:return None
 d=json.loads(p.stdout)[0]
 if d['Config'].get('Labels',{}).get('go2w.desktop')!='mapping-test':raise SystemExit('Container name owned by another workload')
 return d
with (root/'control.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Desktop control request already running')
 action=sys.argv[1];d=inspect();saved=json.loads(state.read_text()) if state.exists() else {}
 if action=='start':
  if d and d['State']['Running']:print(json.dumps(saved));raise SystemExit(0)
  if d:subprocess.run(['docker','rm',name],check=True,stdout=subprocess.DEVNULL)
  run='desktop-'+time.strftime('%Y%m%d-%H%M%S');folder=root/'runs'/run;folder.mkdir(parents=True,exist_ok=False)
  args=['docker','run','-d','--init','--name',name,'--label','go2w.desktop=mapping-test','--network','host','--user',str(os.getuid())+':'+str(os.getgid()),'-e','HOME=/tmp','-e','GO2W_DESKTOP_RUN='+run,'-v',str(root)+':/work','go2w-livo-desktop:20260928','bash','-c','source /work/ws/devel/setup.bash; exec python3 /work/run_inside.py']
  subprocess.run(args,check=True);saved=dict(run=run,folder=str(folder),container=name);state.write_text(json.dumps(saved));print(json.dumps(saved))
 elif action=='stop':
  if d and d['State']['Running']:
   # Send TERM without docker's timed forced KILL, preserving bag sealing.
   subprocess.run(['docker','kill','--signal=TERM',name],check=True,stdout=subprocess.DEVNULL)
   deadline=time.monotonic()+40
   while time.monotonic()<deadline:
    current=inspect()
    if not current or not current['State']['Running']:break
    time.sleep(.2)
   else:raise SystemExit('Desktop still stopping; preserve power and check runtime.json')
  print('Desktop mapping stopped')
 elif action=='status':
  out=dict(saved,running=bool(d and d['State']['Running']))
  for key in ['runtime','health','transport']:
   p=Path(saved.get('folder','/nonexistent'))/(key+'.json')
   if p.exists():out[key]=json.loads(p.read_text())
  if 'health' in out:out['health']['current_age_s']=time.time()-out['health']['updated'];out['ready']=out['running'] and out['health'].get('ready',False) and out['health']['current_age_s']<2
  print(json.dumps(out,ensure_ascii=False,indent=2))
 else:raise SystemExit('start/stop/status')
