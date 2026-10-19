#!/usr/bin/env python3
"""Select a stopped Nav2's profile; never restart localization or send movement."""
import fcntl,json,os,subprocess,sys,tempfile
from pathlib import Path
from contextlib import ExitStack
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'navigation/mppi'))
from speed_profiles import profile

def ensure_stopped(run=subprocess.run):
    # Daemon/permission errors must not be interpreted as an absent container.
    p=run(['docker','ps','-a','--filter','name=^/go2w-nav2-mppi$','--format','{{.ID}}'],capture_output=True,text=True,timeout=8)
    if p.returncode:raise RuntimeError('无法确认导航已停止：'+p.stderr.strip())
    if not p.stdout.strip():return
    p=run(['docker','inspect','-f','{{.State.Running}}','go2w-nav2-mppi'],capture_output=True,text=True,timeout=8)
    if p.returncode or p.stdout.strip() not in ('true','false'):raise RuntimeError('无法读取导航容器状态，未更改速度')
    if p.stdout.strip()=='true':raise RuntimeError('请先停止导航服务，再切换速度档；不在运行中更改配置')

def atomic(path,data):
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        temp=Path(f.name);f.write(data)
    try:os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def select(name,root=ROOT):
    q=profile(name);m=root/'navigation/mppi'
    with ExitStack() as stack:
        # Same lock order as console -> lifecycle; never change a running config.
        for path in (root/'demo/console.lock',m/'control.lock'):
            lock=stack.enter_context(path.open('a'))
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('导航/网页操作正在进行，请完成或取消后再调速')
        ensure_stopped()
        current=m/'current.json'
        if current.exists():
            folder=Path(json.loads(current.read_text())['folder'])
            if any((folder/n).exists() for n in ('motion_active','route_active.json')):
                raise RuntimeError('仍有运动任务标记，请先确认任务结束')
        paths=[m/'speed_profile.json',m/'params.yaml',m/'demo_nav.yaml',root/'demo/state.json']
        before={p:p.read_bytes() if p.exists() else None for p in paths}
        try:
            atomic(paths[0],json.dumps({'name':name}).encode())
            for output in paths[1:3]:
                with tempfile.TemporaryDirectory(dir=m) as tmp:
                    staged=Path(tmp)/'params.yaml'
                    subprocess.run(['/usr/bin/python3',str(m/'make_config.py'),'--output',str(staged)],check=True,timeout=15)
                    atomic(output,staged.read_bytes())
            state=paths[-1]
            if state.exists():
                d=json.loads(state.read_text());d.update(preview=None,route_preview=None)
                atomic(state,json.dumps(d,ensure_ascii=False,indent=2).encode())
        except BaseException:
            for p,value in before.items():
                if value is None:p.unlink(missing_ok=True)
                else:atomic(p,value)
            raise
    print('已选择 '+name+'：前进上限 '+str(q['vx_max'])+' m/s，角速度上限0.8 rad/s。需启动导航、确认定位并重新预演；未启动运动。')

if __name__=='__main__':
    try:select(sys.argv[1] if len(sys.argv)>1 else 'baseline')
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit(str(e))
