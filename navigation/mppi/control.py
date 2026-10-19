"""Lifecycle for isolated no-actuation Nav2/MPPI. Names and labels enforce ownership."""
import os,sys,json,time,subprocess,fcntl,yaml
from speed_profiles import from_config
import status_store
from pathlib import Path
root=Path(__file__).resolve().parent;project=root.parent.parent;state=root/'runs';state.mkdir(exist_ok=True)
sys.path.insert(0,str(project/'lifecycle'))
import compute_backend
board=compute_backend.onboard(project)
name='go2w-nav2-mppi';label='go2w.mppi';image='go2w-nav2-mppi:humble'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def inspect():
 p=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
 if p.returncode:return None
 d=json.loads(p.stdout)[0]
 if d['Config'].get('Labels',{}).get(label)!='preview':raise SystemExit('Container ownership mismatch')
 return d
def source_stop():
 if board:return # Native exporter belongs to the fusion supervisor.
 # Remove only this adapter process, never the ROS master or other mapping children.
 subprocess.run(['docker','exec','go2w-livo-desktop','pkill','-TERM','-f','^python3 /tmp/mppi_source/source_ros1.py$'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for _ in range(30):
  p=subprocess.run(['docker','exec','go2w-livo-desktop','pgrep','-f','^python3 /tmp/mppi_source/source_ros1.py$'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if p.returncode:break
  time.sleep(.1)
 else:raise SystemExit('MPPI exporter still stopping; do not start a duplicate')

with (root/'control.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('MPPI lifecycle operation already running')
 action=sys.argv[1] if len(sys.argv)>1 else 'status';d=inspect()
 if action in ('start','simulation'):
  mode='live' if action=='start' else 'simulation'
  if d and d['State']['Running']:
   old=dict(x.split('=',1) for x in d['Config']['Env'])
   if old.get('MPPI_MODE')!=mode:raise SystemExit('Stop the existing MPPI mode before switching')
   print('MPPI already running; reusing owned container');raise SystemExit(0)
  if mode=='simulation' and (root/'selection.json').exists():raise SystemExit('Saved map selected; use a separate config for simulation to preserve localization')
  run(['docker','image','inspect',image],stdout=subprocess.DEVNULL)
  config_name=os.environ.get('GO2W_MPPI_CONFIG','/work/params.yaml')
  if not config_name.startswith('/work/'):raise SystemExit('Config must be mounted under /work')
  config_path=root/config_name[len('/work/'):]
  config_text=config_path.read_text();speed=from_config(yaml.safe_load(config_text))
  session='simulation'
  if mode=='live':
   s=json.loads(subprocess.check_output(['/usr/bin/python3',str(compute_backend.control(project)),'status']))
   if not s.get('ready'):
    entry='板载运行.sh fusion-start' if board else '本机建图测试.sh start'
    raise SystemExit('FAST-LIVO2尚未就绪，请保持静止并运行：bash '+entry)
   session=s['run'];source_stop()
   if not board:
    # docker cp avoids requiring any change to the existing mapping container mounts.
    run(['docker','exec','go2w-livo-desktop','mkdir','-p','/tmp/mppi_source'])
    run(['docker','cp',str(root/'source_ros1.py'),'go2w-livo-desktop:/tmp/mppi_source/source_ros1.py'])
    run(['docker','exec','-d','-e','GO2W_MPPI_SESSION='+session,'go2w-livo-desktop','bash','-c','source /work/ws/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11331 ROS_IP=127.0.0.1; exec python3 /tmp/mppi_source/source_ros1.py > /tmp/mppi_source.log 2>&1'])
  if d:run(['docker','rm',name],stdout=subprocess.DEVNULL)
  folder=state/(mode+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid()));folder.mkdir()
  if board:status_store.prepare(folder)
  (folder/'active_params.yaml').write_text(config_text)
  (folder/'motion_profile.json').write_text(json.dumps(speed))
  (root/'current.json').write_text(json.dumps(dict(folder=str(folder),mode=mode,session=session)))
  args=['docker','run','-d','--init','--name',name,'--label',label+'=preview','--network','host','--ipc','host','--user',f'{os.getuid()}:{os.getgid()}',
   '-e','GO2W_COMPUTE_BACKEND='+('board' if board else 'desktop'),'-e','MPPI_MODE='+mode,'-e','MPPI_SESSION='+session,'-e','GO2W_MPPI_CONFIG=/state/active_params.yaml','-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=2',
   '-v',str(project/'board')+':/board:ro','-v',str(root)+':/work:ro','-v',str(folder)+':/state','-v',str(project/('board/calibration' if board else 'desktop'))+':/desktop:ro',image]
  run(args)
  if board:
   view_args=['/usr/bin/python3',str(project/'board/saved_view.py'),'start']
   if (root/'selection.json').exists():view_args+=['--map-id',json.loads((root/'selection.json').read_text())['map_id']]
   run(view_args)
  print('Isolated ROS_DOMAIN_ID=79; no robot actuation. Logs: '+str(folder))
 elif action=='stop':
  if d and d['State']['Running']:run(['docker','stop','-t','8',name],stdout=subprocess.DEVNULL)
  if d:
   for mount in d.get('Mounts',[]):
    if mount.get('Destination')=='/state':status_store.finalize(Path(mount['Source']))
  source_stop();print('MPPI stopped; FAST-LIVO2 preserved')
 elif action=='status':
  out=dict(running=bool(d and d['State']['Running']),actuation_enabled=False)
  if (root/'current.json').exists():
   out.update(json.loads((root/'current.json').read_text()))
   for n in ['runtime','input','lifecycle','localization','motion_profile']:
    p=Path(out['folder'])/(n+'.json')
    if p.exists():out[n]=json.loads(p.read_text())
  marker=Path(out.get('folder','/nonexistent'))/'motion_active'
  if marker.exists():
   out['motion']=json.loads(marker.read_text());out['actuation_enabled']=bool(out['motion'].get('execute'))
  out['ready']=out['running'] and out.get('runtime',{}).get('phase')=='running' and 0<=time.time()-out.get('runtime',{}).get('updated',0)<2 and all(out.get(n,{}).get('ready',False) and 0<=time.time()-out[n].get('updated',0)<2 for n in (('input','lifecycle','localization') if (root/'selection.json').exists() else ('input','lifecycle')))
  print(json.dumps(out,ensure_ascii=False,indent=2))
 else:raise SystemExit('start/simulation/stop/status')
