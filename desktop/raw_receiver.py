"""Receive calibrated-format inputs; rebase all absolute timestamps by one offset."""
import socket,struct,time,json,sys
from pathlib import Path
import numpy as np,rospy
from sensor_msgs.msg import Imu,PointCloud2,CompressedImage
from rosgraph_msgs.msg import Clock
from backlog_policy import BacklogGuard
guards=[BacklogGuard() for _ in range(3)];metrics={}
rospy.init_node('desktop_raw_sensor_import')
clock_pub=rospy.Publisher('/clock',Clock,queue_size=10)
classes=[Imu,PointCloud2,CompressedImage];pubs=[rospy.Publisher(t,c,queue_size=2000 if i==0 else 10) for i,(t,c) in enumerate(zip(['/go2w_lio/imu','/go2w_lio/points','/go2w_livo/jpeg'],classes))]
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  a=c.recv(n-len(b))
  if not a:raise EOFError('Sensor connection closed')
  b.extend(a)
 return bytes(b)
with socket.create_connection(('127.0.0.1',11329),timeout=5) as c:
 c.settimeout(3);samples=[]
 for _ in range(5):
  t=time.time();c.sendall(b'T');remote=struct.unpack('!d',exact(c,8))[0];end=time.time();samples.append((end-t,(t+end)/2-remote))
 rtt,offset=min(samples);print(json.dumps(dict(clock_offset=offset,min_rtt_s=rtt)),flush=True);counts=[0,0,0];last=0
 while not rospy.is_shutdown():
  kind,n,sent=struct.unpack('!BId',exact(c,13))
  # Drive ROS time from the same source clock as all sensor stamps.
  # The fixed epoch offset preserves every sensor interval; host drift is not sensor delay.
  clock_pub.publish(Clock(clock=rospy.Time.from_sec(sent+offset)))
  if kind>2 or n>16000000:raise ValueError('Invalid sensor packet')
  m=classes[kind]();m.deserialize(exact(c,n));m.header.stamp=rospy.Time.from_sec(m.header.stamp.to_sec()+offset)
  if kind==1:
   field=next(f for f in m.fields if f.name=='timestamp')
   if field.datatype!=8 or m.is_bigendian:raise ValueError('Expected float64 little-endian absolute point timestamp')
   b=bytearray(m.data);a=np.ndarray((m.width,),dtype='<f8',buffer=b,offset=field.offset,strides=(m.point_step,));a+=offset;m.data=bytes(b)
  age=sent+offset-m.header.stamp.to_sec()
  phase=guards[kind].check(age,time.monotonic())
  metrics[['imu','cloud','jpeg'][kind]]=dict(age_s=age,phase=phase,count=counts[kind]+1)
  if phase=='catching_up':rospy.logwarn_throttle(1,'Catching up sensor %d age %.3fs; navigation must remain age-gated'%(kind,age))
  pubs[kind].publish(m);counts[kind]+=1
  if time.monotonic()-last>1:
   state_path=Path(sys.argv[1]);tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(per_topic=metrics,counts=counts,clock_offset=offset,min_rtt_s=rtt,last_input_age_s=age,host_clock_difference_s=time.time()-(sent+offset),updated=time.time())));tmp.replace(state_path);last=time.monotonic()
