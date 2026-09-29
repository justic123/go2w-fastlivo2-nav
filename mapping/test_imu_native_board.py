"""Run with ROS1 env, isolated master, never on the robot's sensor master."""
import json,os,signal,subprocess,tempfile,time
from pathlib import Path
import xmlrpc.client
def main():
 root=Path(__file__).parent
 with tempfile.TemporaryDirectory() as d:
  env=dict(os.environ,ROS_MASTER_URI='http://127.0.0.1:11341',ROS_IP='127.0.0.1',ROS_HOSTNAME='localhost',ROS_LOG_DIR=d)
  log=open(Path(d)/'master.log','w')
  master=subprocess.Popen(['/opt/ros/noetic/bin/roscore','-p','11341'],env=env,stdout=log,stderr=log,start_new_session=True)
  try:
   for _ in range(100):
    try:
     if xmlrpc.client.ServerProxy(env['ROS_MASTER_URI']).getPid('/native_test')[0]==1:break
    except OSError:pass
    time.sleep(.1)
   else:raise RuntimeError('isolated master timeout')
   header='receive_unix_ns,receive_monotonic_ns,tick,gx,gy,gz,ax,ay,az,qw,qx,qy,qz\n'
   def row(i,g='0'):return f'{1000000000+i*2000000},{i*2000000},{i*2},{g},0,.1,0,0,9.81,1,0,0,0\n'
   cases=[('ordered', ''.join(row(i) for i in range(700)),201,'IMU source ended unexpectedly'),('nan',''.join(row(i) for i in range(600))+row(600,'nan'),101,'Nonfinite IMU'),('reset',''.join(row(i) for i in range(600))+row(10),101,'Tick reset/wrap: stop and reinitialize explicitly'),('duplicate',''.join(row(i) for i in range(600))+row(599),101,'IMU source ended unexpectedly')]
   for name,body,count,reason in cases:
    out=Path(d)/name;out.mkdir()
    r=subprocess.run([str(root/'imu_forward_native'),str(out)],input=header+body,text=True,env=env,timeout=15,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    s=json.loads((out/'imu_summary.json').read_text())
    assert r.returncode==1,(name,r.returncode,r.stderr)
    assert s['imu_published']==count,(name,s)
    assert s['failure']==reason,(name,s)
    assert abs(s['tick_anchor']-1)<1e-6,s
    if name=='duplicate':assert s['duplicate_ticks_dropped']==1,s
    print(name,'PASS',flush=True)
  finally:
   os.killpg(master.pid,signal.SIGTERM)
   try:master.wait(timeout=8)
   except subprocess.TimeoutExpired:os.killpg(master.pid,signal.SIGKILL);master.wait()
   log.close()

if __name__=='__main__':main()
