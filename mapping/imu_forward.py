#!/usr/bin/env python3
"""Independent ordered IMU forwarding. No cloud processing or motion interfaces."""
import csv,json,os,signal,subprocess,time,sys
from pathlib import Path
import numpy as np
import rospy
from sensor_msgs.msg import Imu
from input_core import TickClock

def main():
 out=Path(sys.argv[1]);rospy.init_node('go2w_imu_forward')
 pub=rospy.Publisher('/go2w_lio/imu',Imu,queue_size=1000)
 clock=TickClock();stop=False;failure=None;proc=None
 stats=dict(imu_published=0,max_receipt_tick_residual_ms=0.,max_source_to_reader_s=0.,max_publish_s=0.)
 def terminate(*_):
  nonlocal stop
  stop=True
  if proc is not None and proc.poll() is None:proc.terminate()
 signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
 shell='source /opt/ros/foxy/setup.bash; source /home/unitree/cyclonedds_ws/install/setup.bash; source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml; exec /home/unitree/fast_livo2_port/build1/mapping/imu_build/ros2_imu_source 0'
 env=dict(HOME='/home/unitree',USER='unitree',LANG='C.UTF-8',PATH='/usr/bin:/bin')
 try:
  with (out/'imu-source.stderr').open('w') as err,(out/'imu_timing.csv').open('w') as timing,(out/'imu_forward_timing.jsonl').open('w',buffering=1) as metrics:
   timing.write('wall_ns,mono_ns,tick\n')
   proc=subprocess.Popen(['/bin/bash','--noprofile','--norc','-c',shell],env=env,stdout=subprocess.PIPE,stderr=err)
   last=0.
   for row in csv.DictReader(b.decode() for b in iter(proc.stdout.readline,b'')):
    if stop or rospy.is_shutdown():break
    entered=time.time();receipt=int(row['receive_unix_ns'])*1e-9
    timing.write(row['receive_unix_ns']+','+row['receive_monotonic_ns']+','+row['tick']+'\n')
    vals=[float(row[k]) for k in ['gx','gy','gz','ax','ay','az']]
    if not np.isfinite(vals).all():raise ValueError('Nonfinite IMU')
    ts=clock.observe(int(row['tick']),receipt)
    if ts is None:continue
    residual=(receipt-ts)*1000
    if abs(residual)>500:raise ValueError('Tick/host alignment exceeds 500ms guard')
    m=Imu();m.header.stamp=rospy.Time.from_sec(ts);m.header.frame_id='body_imu_candidate';m.orientation_covariance[0]=-1
    m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z=vals[:3];m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z=vals[3:]
    before=time.monotonic();pub.publish(m);duration=time.monotonic()-before
    stats['imu_published']+=1
    stats['max_receipt_tick_residual_ms']=max(stats['max_receipt_tick_residual_ms'],residual)
    stats['max_source_to_reader_s']=max(stats['max_source_to_reader_s'],entered-receipt)
    stats['max_publish_s']=max(stats['max_publish_s'],duration)
    if time.monotonic()-last>.5:
     d=dict(updated=time.time(),stamp=ts,source_to_reader_s=entered-receipt,publish_s=duration,source_age_s=time.time()-ts,**stats)
     metrics.write(json.dumps(d)+'\n');tmp=out/'imu_health.tmp';tmp.write_text(json.dumps(d));tmp.replace(out/'imu_health.json');last=time.monotonic()
   if not stop and not rospy.is_shutdown():raise RuntimeError('IMU source ended unexpectedly')
 except Exception as e:failure=str(e)
 finally:
  if proc is not None:
   if proc.poll() is None:proc.terminate()
   try:proc.wait(timeout=3)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  stats.update(failure=failure,duplicate_ticks_dropped=clock.duplicates,tick_anchor=clock.anchor)
  (out/'imu_summary.json').write_text(json.dumps(stats,indent=2));rospy.signal_shutdown('IMU forward stopped')
 if failure:raise SystemExit(failure)
if __name__=='__main__':main()
