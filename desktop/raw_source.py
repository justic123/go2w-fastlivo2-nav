"""Loopback-only loss-detecting sensor transport, forwarded by SSH. No actuation."""
import io,json,queue,socket,struct,time,threading,sys
from pathlib import Path
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
 q=queue.Queue(1200);failed=threading.Event();counts=dict(imu=0,cloud=0,jpeg=0);subs=[]
 def cb(m,kind):
  b=io.BytesIO();m.serialize(b)
  try:q.put_nowait((kind,b.getvalue(),time.monotonic()))
  except queue.Full:failed.set()
 try:
  c.settimeout(2)
  # Five round trips establish a fixed wall-clock offset at the receiving PC.
  for _ in range(5):exact(c,1);c.sendall(struct.pack('!d',time.time()))
  for kind,topic,cls in [(0,'/go2w_lio/imu',Imu),(1,'/go2w_lio/points',PointCloud2),(2,'/go2w_livo/jpeg',CompressedImage)]:
   subs.append(rospy.Subscriber(topic,cls,lambda m,k=kind:cb(m,k),queue_size=1000 if kind==0 else 4,buff_size=8*1024*1024,tcp_nodelay=True))
  last=0
  while not rospy.is_shutdown() and not failed.is_set():
   try:kind,data,queued=q.get(timeout=.2)
   except queue.Empty:continue
   if time.monotonic()-queued>1:raise RuntimeError('Sensor forwarding backlog >1s; disconnect rather than silently discard IMU')
   c.sendall(struct.pack('!BId',kind,len(data),time.time())+data);counts[['imu','cloud','jpeg'][kind]]+=1
   if time.monotonic()-last>.5:
    t=status.with_suffix('.tmp');t.write_text(json.dumps(dict(counts=counts,updated=time.time(),queue=q.qsize(),connected=True)));t.replace(status);last=time.monotonic()
 except (OSError,EOFError,RuntimeError) as e:print(str(e),flush=True)
 finally:
  for sub in subs:sub.unregister()
  c.close()
