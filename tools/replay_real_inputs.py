#!/usr/bin/env python3
"""Diagnostic hypotheses only: ns point offsets; tick-ms aligned to median receipt."""
import csv,json,sys,time,threading
from pathlib import Path
import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2,PointField,Imu
from nav_msgs.msg import Odometry
src,out=map(Path,sys.argv[1:3]);mode=sys.argv[3];assert mode in ['start','end']
frames=json.loads((src/'frames.json').read_text());rows=list(csv.DictReader((src/'lowstate.csv').open()))
ticks=np.array([int(r['tick']) for r in rows],dtype=np.int64)
receipt=np.array([int(r['receive_unix_ns']) for r in rows],dtype=np.int64)/1e9
ticksec=(ticks-ticks[0])/1000.
anchor=float(np.median(receipt-ticksec))
base=frames[0]['stamp_sec']+frames[0]['stamp_nanosec']/1e9-1
rospy.init_node('real_recorded_replay')
lidar=rospy.Publisher('/fast_livo2_smoke/no_lidar',PointCloud2,queue_size=5)
imu=rospy.Publisher('/fast_livo2_smoke/no_imu',Imu,queue_size=1000)
odoms=[]
def cb(m):
 p=m.pose.pose.position;q=m.pose.pose.orientation
 odoms.append([time.monotonic(),p.x,p.y,p.z,q.x,q.y,q.z,q.w])
sub=rospy.Subscriber('/aft_mapped_to_init',Odometry,cb,queue_size=1000)
limit=time.monotonic()+15
while not (lidar.get_num_connections() and imu.get_num_connections()):
 assert time.monotonic()<limit,'Missing algorithm subscribers'
 time.sleep(.1)
events=[];last=-1;duplicates=0
for i,t in enumerate(anchor+ticksec):
 if ticks[i]<=last:duplicates+=1;continue
 last=ticks[i]
 if base<=t<=base+17:events.append((float(t),1,i))
for i,r in enumerate(frames):
 h=r['stamp_sec']+r['stamp_nanosec']/1e9
 # Offline scheduling: publish each full scan at reconstructed start, before its IMU interval.
 # This deliberately does not reproduce DDS arrival jitter.
 events.append((h-r['point_stats']['time_max']*1e-9 if mode=='end' else h,0,i))
events.sort();first=events[0][0];wall=time.monotonic();speed=.5
fields=[PointField(n,o,t,1) for n,o,t in [('x',0,7),('y',4,7),('z',8,7),('intensity',12,7),('ring',16,4),('timestamp',18,8)]]
outdtype=np.dtype({'names':['x','y','z','intensity','ring','timestamp'],'formats':['<f4','<f4','<f4','<f4','<u2','<f8'],'offsets':[0,4,8,12,16,18],'itemsize':26})
for t,typ,i in events:
 time.sleep(max(0,wall+(t-first)/speed-time.monotonic()))
 if typ:
  r=rows[i];m=Imu();m.header.stamp=rospy.Time.from_sec(t-base+1000);m.header.frame_id='recorded_body_imu'
  m.orientation.w=float(r['qw']);m.orientation.x=float(r['qx']);m.orientation.y=float(r['qy']);m.orientation.z=float(r['qz'])
  m.angular_velocity.x=float(r['gx']);m.angular_velocity.y=float(r['gy']);m.angular_velocity.z=float(r['gz'])
  m.linear_acceleration.x=float(r['ax']);m.linear_acceleration.y=float(r['ay']);m.linear_acceleration.z=float(r['az']);imu.publish(m)
 else:
  a=np.load(src/f'{i:04d}.npy');valid=np.isfinite(a['time'])&(a['ring']<16)
  for k in ['x','y','z','intensity']:valid &= np.isfinite(a[k])
  a=a[valid];a=a[np.argsort(a['time'],kind='stable')]
  offset=a['time'].astype(float)*1e-9
  assert len(a)>1 and offset[0]>=0 and offset[-1]<.2
  h=frames[i]['stamp_sec']+frames[i]['stamp_nanosec']/1e9
  start=h-(offset[-1] if mode=='end' else 0)
  data=np.empty(len(a),dtype=outdtype)
  for k in ['x','y','z','intensity','ring']:data[k]=a[k]
  data['timestamp']=start-base+1000+offset
  m=PointCloud2();m.header.stamp=rospy.Time.from_sec(start-base+1000);m.header.frame_id='recorded_xt16'
  m.height=1;m.width=len(a);m.fields=fields;m.point_step=26;m.row_step=26*len(a);m.is_dense=True;m.data=data.tobytes();lidar.publish(m)
time.sleep(5)
arr=np.asarray(odoms);finite=bool(len(arr) and np.isfinite(arr).all())
result=dict(diagnostic_only=True,header_hypothesis=mode,point_time_assumption='nanosecond offsets, stable sorted',imu_time_assumption='1ms tick, median receipt anchor; unknown sampling latency',replay_speed=speed,input_frames=len(frames),dropped_nonincreasing_ticks=duplicates,odometry_count=len(arr),all_finite=finite)
if finite:
 result.update(max_position_norm_m=float(np.linalg.norm(arr[:,1:4],axis=1).max()),final_position_m=arr[-1,1:4].tolist())
out.write_text(json.dumps(result,indent=2)+'\n');np.save(out.with_suffix('.npy'),arr);print(json.dumps(result,indent=2))
assert finite and len(arr)>=100,'Insufficient finite odometry output'
