#!/usr/bin/env python3
"""Own two native processes; Python does not parse or publish individual IMUs."""
import os,signal,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]);stop=False;source=None;sink=None

def terminate(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
shell='source /opt/ros/foxy/setup.bash; source /home/unitree/cyclonedds_ws/install/setup.bash; source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml; exec /home/unitree/fast_livo2_port/build1/mapping/imu_build/ros2_imu_source 0'
try:
 with (out/'imu-source.stderr').open('w') as err:
  source=subprocess.Popen(['/bin/bash','--noprofile','--norc','-c',shell],env=dict(HOME='/home/unitree',USER='unitree',LANG='C.UTF-8',PATH='/usr/bin:/bin'),stdout=subprocess.PIPE,stderr=err)
  sink=subprocess.Popen([str(Path(__file__).with_name('imu_forward_native')),str(out)],stdin=source.stdout)
  source.stdout.close()
  while not stop and source.poll() is None and sink.poll() is None:time.sleep(.1)
finally:
 for proc in (sink,source):
  if proc is not None and proc.poll() is None:proc.terminate()
 for proc in (sink,source):
  if proc is not None:
   try:proc.wait(timeout=2)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
if not stop:raise SystemExit('Native IMU pipeline ended unexpectedly')
