#!/usr/bin/env python3
"""Authenticated LAN dashboard. No arbitrary commands, paths, or ROS publishing."""
import sys
import fcntl
import atexit, hashlib, hmac, json, mimetypes, os, secrets, signal, subprocess, threading, time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from common import ROOT,STATE,CACHE,read,atomic,fresh,pose,name
STATIC=PathStatic=ROOT/'board/web/static'
ACTIONS={'anchor-save','anchor-use','anchor-delete','delete-map','restore-map','start','finish','load-map','restore','assist','record','map-point','preview','navigate','route-set','route-preview','route-execute','route-resume-preview','route-resume','point-settings'}
MOTION={'navigate','route-execute','route-resume'}
ASSETS={'grid.png','local.png','saved.png','cloud.bin','saved-cloud.bin','rgb-cloud.bin','saved-rgb.bin','camera.jpg'}
STATE.mkdir(parents=True,exist_ok=True);CACHE.mkdir(exist_ok=True)
secret_file=STATE/'access-key'
if not secret_file.exists():
    fd=os.open(str(secret_file),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(18))
KEY=secret_file.read_text().strip()
lock=threading.RLock();job=None;worker=None;sessions={};failures={};stopping=False;generation=0

def current_folder():return PathFolder(read(ROOT/'navigation/mppi/current.json').get('folder','/nonexistent'))
def PathFolder(p):
    from pathlib import Path
    return Path(p)

def stop_action(reason='用户请求停车'):
    global stopping,generation
    with lock:
        generation+=1
        if stopping:return
        stopping=True
        p=worker
        if job and job.get('phase')=='running':job['message']=reason;job['cancelled']=True
    def cancel():
        global stopping
        try:
            if p and p.poll() is None:os.killpg(p.pid,signal.SIGINT)
            result=subprocess.run(['/usr/bin/python3',str(ROOT/'board/web/action.py')],input=json.dumps({'action':'stop'}),text=True,cwd=ROOT,capture_output=True,timeout=18)
            atomic(STATE/'last-stop.json',dict(at=time.time(),confirmed=result.returncode==0,reason=reason,detail=(result.stdout+result.stderr)[-2000:]))
        except Exception as e:atomic(STATE/'last-stop.json',dict(at=time.time(),confirmed=False,reason=reason,detail=str(e)))
        finally:
            with lock:stopping=False
    threading.Thread(target=cancel,daemon=True).start()

def begin(req,owner):
    global job,worker
    action=req.get('action')
    if action not in ACTIONS:raise ValueError('不支持的操作')
    if action=='delete-map' and req.get('confirm_delete') is not True:raise ValueError('请确认删除地图')
    if action in MOTION and req.get('confirm_motion') is not True:raise ValueError('需要明确确认实际运动')
    if action in ('start','finish','restore','assist','anchor-save','anchor-use') and req.get('stationary') is not True:raise ValueError('请先确认静止')
    if action in ('anchor-save','anchor-use','anchor-delete','record','map-point','navigate','preview','point-settings'):name(req.get('name'))
    if action in ('assist','map-point'):pose(req.get('pose'))
    if action=='anchor-use' and req.get('confirm_placement') is not True:raise ValueError('请确认固定位置和朝向')
    if action=='anchor-delete' and req.get('confirm_delete') is not True:raise ValueError('请确认删除固定定位点')
    with lock:
        if stopping or (worker and worker.poll() is None):raise ValueError('已有操作执行中，请等待完成或停止')
        if req.get('generation')!=generation:raise ValueError('操作页面已过期，请刷新后重试')
        if action in MOTION and time.monotonic()-sessions.get(owner,{}).get('seen',0)>3:raise ValueError('网页连接未续约，禁止开始运动')
        ident=secrets.token_hex(8);log=STATE/(ident+'.log')
        f=log.open('w');p=subprocess.Popen(['/usr/bin/python3',str(ROOT/'board/web/action.py')],stdin=subprocess.PIPE,stdout=f,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
        job=dict(id=ident,action=action,phase='running',started=time.time(),owner=owner,cancelled=False)
        worker=p
        p.stdin.write(json.dumps(req).encode());p.stdin.close()
        def finish():
            code=p.wait();f.close()
            with lock:
                if job and job['id']==ident:
                    job.update(phase='cancelled' if job['cancelled'] else 'done' if code==0 else 'failed',returncode=code,ended=time.time())
                    atomic(STATE/'last-job.json',{k:v for k,v in job.items() if k!='owner'})
        threading.Thread(target=finish,daemon=True).start()
        return ident

def console_busy():
    # CLI and web share one lock; show an external in-progress action truthfully.
    with (ROOT/'demo/console.lock').open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        return False

def snapshot():
    d=read(ROOT/'demo/state.json');fc=read(ROOT/'board/current.json');nf=current_folder();ff=PathFolder(fc.get('folder','/nonexistent'))
    fusion=read(ff/'health.json');fr=read(ff/'runtime.json');inp=read(nf/'input.json');loc=read(nf/'localization.json');life=read(nf/'lifecycle.json');nr=read(nf/'runtime.json')
    fusion_ok=fresh(fusion) and fr.get('phase')=='running' and 0<=time.time()-fr.get('updated',0)<2
    nav_ok=inp.get('session')==fc.get('run') and fresh(inp) and fresh(life) and nr.get('phase')=='running' and 0<=time.time()-nr.get('updated',0)<2
    localized=nav_ok and fresh(loc) and loc.get('map_id')==d.get('map_id') and loc.get('source_session')==fc.get('run') and d.get('session')==fc.get('run')
    ready=bool(fusion_ok and localized and d.get('phase')=='navigation')
    from camera_policy import status as camera_status
    view=read(CACHE/'view.json');camera=camera_status(read(ROOT/'board/deployment.json'),read(CACHE/'camera.json'),fc.get('run'))
    with lock:j=dict(job or read(STATE/'last-job.json'));j.pop('owner',None)
    if j.get('id'):
        try:
            with (STATE/(j['id']+'.log')).open('rb') as f:f.seek(max(0,os.fstat(f.fileno()).st_size-6000));j['log']=f.read().decode(errors='replace')
        except OSError:pass
    last_result=read(nf/'last-action-result.json')
    if not (j.get('action') in MOTION and j.get('started',float('inf'))<=last_result.get('finished',0)<=j.get('ended',time.time())+1):last_result={}
    from_path=str(ROOT/'navigation/mppi')
    if from_path not in sys.path:sys.path.insert(0,from_path)
    from motion_modes import point_fingerprint
    from go2w_mode_adapter import Go2WModeAdapter
    from speed_profiles import selected
    speed=dict(selected=selected(ROOT/'navigation/mppi'),active=read(nf/'motion_profile.json') if nav_ok else None)
    supported=sorted(Go2WModeAdapter().supported_modes())
    fingerprints={n:point_fingerprint(t) for n,t in d.get('points',{}).items()}
    maps=[p.name for p in (ROOT/'navigation/mppi/maps').iterdir() if p.is_dir() and all((p/n).exists() for n in ('map.yaml','points.npy','map.pgm'))]
    sys.path.insert(0,str(ROOT/'demo')) if str(ROOT/'demo') not in sys.path else None
    import map_store,localization_anchors,mission
    from types import SimpleNamespace
    catalog=SimpleNamespace(MPPI=ROOT/'navigation/mppi',read=read)
    continuation=mission.resume_status(SimpleNamespace(state=lambda:d,folder=lambda:nf,read=read))
    versions={}
    for ident in maps:
        try:versions[ident]=map_store.version(catalog,ident)
        except (OSError,ValueError):pass
    map_meta=read(ROOT/'navigation/mppi/maps'/d['map_id']/'metadata.json') if d.get('map_id') else {}
    map_geometry_warning=('此地图由旧保存方式生成，可能含重复膨胀。修复后请重新扫图保存；当前地图和目标保留。' if map_meta.get('note')=='Observed navigation costmap snapshot; unknown preserved, inflation recomputed' and map_meta.get('occupancy_encoding')!='lethal_only_v2' else '')
    anchors={};anchor_error=''
    if d.get('map_id'):
        try:anchors=localization_anchors.entries(catalog,d['map_id'])
        except (OSError,ValueError,KeyError) as e:anchor_error=str(e)
    return dict(resume=continuation,map_geometry_warning=map_geometry_warning,anchors=anchors,anchor_error=anchor_error,external_operation=console_busy(),map_versions=versions,trash=map_store.trash_entries(catalog),generation=generation,now=time.time(),compute='Go2W 板载',speed=speed,point_fingerprints=fingerprints,state=d,maps=sorted(maps,reverse=True),fusion_ready=fusion_ok,nav_ready=nav_ok,localized=localized,ready=ready,
                motion_modes=dict(supported=supported,note='到点停稳后切换，并等待实机状态确认后继续。' if supported else '到点切换参数可保存；当前板端接口尚未验证，切换目标会在执行前拒绝'),fusion=fusion,input=inp,localization=loc,nav_runtime=nr,view=view,camera=camera,job=j,stopping=stopping,last_result=last_result,last_stop=read(STATE/'last-stop.json'),route_progress=read(nf/'route_progress.json'))

def heartbeat_lost(current,clients,now):
    return bool(current and current.get('phase')=='running' and current.get('action') in MOTION and now-clients.get(current.get('owner'),{}).get('seen',0)>5)

def watchdog():
    while True:
        time.sleep(.5)
        with lock:
            lost=heartbeat_lost(job,sessions,time.monotonic())
        if lost and not stopping:stop_action('网页控制连接超过5秒未续约，已请求停车')

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(10)
    def log_message(self,*args):pass
    def output(self,code,body,typ='application/json',headers=None):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(code);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def auth(self):
        try:c=SimpleCookie(self.headers.get('Cookie',''));sid=c['go2w_session'].value
        except Exception:return None
        with lock:
            s=sessions.get(sid)
            if not s or time.monotonic()-s['created']>43200:return None
        return sid
    def host_ok(self):
        host=self.headers.get('Host','').split(':')[0]
        return host in ('192.168.123.18','127.0.0.1','localhost')
    def do_GET(self):
        if not self.host_ok():return self.output(403,{'error':'Host不允许'})
        path=urlparse(self.path).path
        if path in ('/','/app.js','/style.css'):
            f=STATIC/({'/':'index.html'}.get(path,path[1:]));return self.output(200,f.read_bytes(),mimetypes.guess_type(str(f))[0] or 'text/plain')
        if not self.auth():return self.output(401,{'error':'请先输入访问码'})
        if path=='/api/status':return self.output(200,snapshot())
        if path.startswith('/data/') and path[6:] in ASSETS:
            f=CACHE/path[6:]
            try:
                tag=str(f.stat().st_mtime_ns)
                if self.headers.get('If-None-Match')==tag:return self.output(304,b'')
                return self.output(200,f.read_bytes(),mimetypes.guess_type(str(f))[0] or 'application/octet-stream',{'ETag':tag})
            except FileNotFoundError:return self.output(404,{'error':'尚无数据'})
        return self.output(404,{'error':'不存在'})
    def do_POST(self):
        if not self.host_ok() or self.headers.get('Origin')!='http://'+self.headers.get('Host',''):return self.output(403,{'error':'仅允许本网页同源操作'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<16384:raise ValueError('请求长度无效')
            req=json.loads(self.rfile.read(size));path=urlparse(self.path).path
            if not isinstance(req,dict):raise ValueError('请求无效')
            if path=='/api/login':
                ip=self.client_address[0];now=time.monotonic()
                with lock:
                    attempts=[t for t in failures.get(ip,[]) if now-t<60]
                    if len(attempts)>=6:return self.output(429,{'error':'尝试过多，请1分钟后重试'})
                    if not hmac.compare_digest(str(req.get('key','')),KEY):failures[ip]=attempts+[now];return self.output(403,{'error':'访问码不正确'})
                    sid=secrets.token_urlsafe(32);sessions[sid]=dict(created=now,seen=now)
                return self.output(200,{'ok':True},'application/json',{'Set-Cookie':'go2w_session='+sid+'; HttpOnly; SameSite=Strict; Path=/'})
            sid=self.auth()
            if not sid:return self.output(401,{'error':'请先登录'})
            if path=='/api/heartbeat':
                with lock:sessions[sid]['seen']=time.monotonic()
                return self.output(200,{'ok':True})
            if path=='/api/stop':stop_action();return self.output(202,{'ok':True})
            if path=='/api/action':return self.output(202,{'job':begin(req,sid)})
            return self.output(404,{'error':'不存在'})
        except (ValueError,KeyError,TypeError) as e:return self.output(400,{'error':str(e)})
        except Exception as e:return self.output(500,{'error':str(e)})

def main():
    if not (ROOT/'board/deployment.json').exists():raise SystemExit('只允许在已部署的Go2W板端运行')
    threading.Thread(target=watchdog,daemon=True).start()
    http=ThreadingHTTPServer(('0.0.0.0',8088),Handler)
    def shutdown(*_):
        stop_action('网页服务关闭');threading.Thread(target=http.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    print('Go2W 网页：http://192.168.123.18:8088',flush=True)
    http.serve_forever()
    end=time.monotonic()+20
    while (stopping or (worker and worker.poll() is None)) and time.monotonic()<end:time.sleep(.1)
    http.server_close()
if __name__=='__main__':main()
