"""Loopback-only loss-detecting sensor transport, forwarded by SSH. No actuation."""
import io,json,queue,socket,struct,time,threading,sys
from pathlib import Path
from backlog_policy import BacklogGuard
from transport_buffer import SensorBuffer
import rospy
from sensor_msgs.msg import Imu,PointCloud2,CompressedImage
rospy.init_node('desktop_raw_sensor_export')
status=Path(sys.argv[1]);server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind(('127.0.0.1',11329));server.listen(1);server.settimeout(1)
def exact(c,n):
 b=b''
 while len(b)<n:
  a=c.recv(n-len(b))
  if not a:raise EOFError()
  b+=a
 return b
while not rospy.is_shutdown():
 try:c,_=server.accept()
 except socket.timeout:continue
 q=SensorBuffer();guard=BacklogGuard();error=None;phase="live";failed=threading.Event();counts=dict(imu=0,cloud=0,jpeg=0);subs=[];metrics={};maxima={}
 def cb(m,kind):
  received=time.time();stamp=m.header.stamp.to_sec();b=io.BytesIO();m.serialize(b)
  try:q.put_nowait((kind,b.getvalue(),time.monotonic(),received,stamp))
  except queue.Full:failed.set()
 try:
  c.settimeout(2)
  # Five round trips establish a fixed wall-clock offset at the receiving PC.
  for _ in range(5):exact(c,1);c.sendall(struct.pack('!d',time.time()))
  for kind,topic,cls in [(0,'/go2w_lio/imu',Imu),(1,'/go2w_lio/points',PointCloud2),(2,'/go2w_livo/jpeg',CompressedImage)]:
   subs.append(rospy.Subscriber(topic,cls,lambda m,k=kind:cb(m,k),queue_size=1000 if kind==0 else 4,buff_size=8*1024*1024,tcp_nodelay=True))
  last=0
  while not rospy.is_shutdown() and not failed.is_set():
   try:kind,data,queued,received,stamp=q.get(timeout=.2)
   except queue.Empty:continue
   phase=guard.check(time.monotonic()-queued,time.monotonic())
   if phase=='catching_up':rospy.logwarn_throttle(1,'Sensor forwarding catching up; retaining all queued packets')
   sent=time.time();before=time.monotonic();c.sendall(struct.pack('!BId',kind,len(data),sent)+data)
   name=['imu','cloud','jpeg'][kind];metrics[name]=dict(source_age_s=received-stamp,queue_age_s=sent-received,send_s=time.monotonic()-before);maxima[name]={k:max(v,maxima.get(name,{}).get(k,0)) for k,v in metrics[name].items()}
   counts[['imu','cloud','jpeg'][kind]]+=1
   if time.monotonic()-last>.5:
    t=status.with_suffix('.tmp');t.write_text(json.dumps(dict(counts=counts,updated=time.time(),connected=True,phase=phase,error=None,per_topic=metrics,maxima=maxima,**q.snapshot())));t.replace(status);last=time.monotonic()
  if failed.is_set():raise RuntimeError('Sensor buffer overflow; stream terminated, no silent sample drop')
 except (OSError,EOFError,RuntimeError) as e:error=type(e).__name__+': '+str(e);print(error,flush=True)
 finally:
  for sub in subs:sub.unregister()
  t=status.with_suffix(".tmp");t.write_text(json.dumps(dict(updated=time.time(),connected=False,counts=counts,phase="disconnected",error=error,per_topic=metrics,maxima=maxima,**q.snapshot())));t.replace(status)
  c.close()
