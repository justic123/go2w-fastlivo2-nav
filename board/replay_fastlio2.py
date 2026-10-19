#!/usr/bin/env python3
"""Isolated recorded-input FAST-LIO2 replay; never launches sensors or SDK."""
import argparse,json,math,os,signal,socket,subprocess,time
from pathlib import Path
from port_check import check_ports


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--bag',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=60);p.add_argument('--start',type=int,default=30);p.add_argument('--port',type=int,default=11431)
    a=p.parse_args()
    if not a.bag.is_file() or not 10<=a.seconds<=600 or not 0<=a.start or not 11400<=a.port<=11999:
        raise ValueError('Invalid isolated replay arguments')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:words=(proc/'cmdline').read_bytes().split(b'\0')
        except OSError:continue
        if words and Path(words[0].decode(errors='replace')).name in ('fastlio_mapping','fastlivo_mapping','xt16_driver'):
            raise RuntimeError('Stop live fusion/capture before offline replay: PID '+proc.name)
    check_ports((a.port,));a.output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,HOME='/home/unitree',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OMP_WAIT_POLICY='PASSIVE')
    raw=subprocess.check_output(['bash','-c','source "$1"; env -0','_',str(a.release/'ws/devel/setup.bash')],env=env)
    env.update(dict(x.decode().split('=',1) for x in raw.split(b'\0') if b'=' in x))
    env.update(ROS_MASTER_URI='http://127.0.0.1:'+str(a.port),ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',ROS_LOG_DIR=str(a.output/'ros_logs'))
    children=[];logs=[];error=None;started=time.monotonic()
    def launch(role,args):
        log=(a.output/(role+'.log')).open('w');logs.append(log)
        child=subprocess.Popen(args,env=env,stdout=log,stderr=log,start_new_session=True);children.append((role,child));return child
    def run(args):subprocess.run(args,env=env,check=True,stdout=subprocess.DEVNULL,timeout=8)
    try:
        launch('master',['roscore','-p',str(a.port)]);end=time.monotonic()+15
        while True:
            try:run(['rosparam','list']);break
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                if time.monotonic()>end:raise RuntimeError('Isolated master unavailable')
                time.sleep(.2)
        run(['rosparam','set','/use_sim_time','true']);run(['rosparam','load',str(a.release/'fastlio.yaml'),'/go2w_lio'])
        launch('observer',['/usr/bin/python3',str(Path(__file__).with_name('profile_sub.py')),str(a.output/'observations.jsonl')])
        algorithm=launch('algorithm',[str(a.release/'ws/devel/lib/fast_lio/fastlio_mapping'),'__ns:=/go2w_lio','/Odometry:=/go2w_lio/odometry','/cloud_registered:=/go2w_lio/cloud'])
        time.sleep(2)
        player=launch('player',['rosbag','play','--clock','--quiet','--start',str(a.start),'--duration',str(a.seconds),str(a.bag),'--topics','/go2w_lio/points','/go2w_lio/imu'])
        end=time.monotonic()+a.seconds+25
        while player.poll() is None:
            if algorithm.poll() is not None:raise RuntimeError('FAST-LIO2 exited during replay')
            if time.monotonic()>end:raise RuntimeError('Recorded-input replay deadline exceeded')
            time.sleep(.2)
        if player.returncode:raise RuntimeError('Replay player failed')
        time.sleep(2)
    except BaseException as exc:error=str(exc) or type(exc).__name__
    finally:
        for role,child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGINT)
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        for log in logs:log.close()
    events=[json.loads(line) for line in (a.output/'observations.jsonl').read_text().splitlines()] if (a.output/'observations.jsonl').exists() else []
    odom=[e['data'] for e in events if e['kind']=='odom'];lag=sorted(e['data']['seconds'] for e in events if e['kind']=='lag')
    invalid=sum(not all(math.isfinite(x) for x in d['pose']) for d in odom)
    gaps=[b['stamp']-a['stamp'] for a,b in zip(odom,odom[1:])]
    drift=max((math.dist(d['pose'][:3],odom[0]['pose'][:3]) for d in odom),default=None)
    summary=dict(error=error,wall_s=time.monotonic()-started,seconds=a.seconds,start=a.start,source_bag=str(a.bag),
                 port=a.port,camera_started=False,drivers_started=False,motion_commands_sent=False,odom_count=len(odom),nonfinite_poses=invalid,
                 nonincreasing_stamps=sum(v<=0 for v in gaps),max_odom_gap_s=max(gaps) if gaps else None,position_span_from_first_m=drift,
                 lag_s=dict(n=len(lag),p50=lag[len(lag)//2],p95=lag[int((len(lag)-1)*.95)],max=lag[-1]) if lag else None)
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
    if error or len(odom)<a.seconds*5 or invalid or any(v<=0 for v in gaps):raise SystemExit(1)


if __name__=='__main__':main()
