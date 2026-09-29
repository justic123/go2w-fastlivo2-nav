#!/usr/bin/env python3
import os,socket,struct,json,time,threading,uuid
import rospy
import numpy as np
from sensor_msgs.msg import PointCloud2,Image,CompressedImage
from nav_msgs.msg import Odometry
# One ID per board display source lifetime; TCP reconnects retain the same map.
session_id=uuid.uuid4().hex
latest={};lock=threading.Lock();last_sent={}
def cb(m,kind):
 if kind=='cloud' and (m.width*m.height==0 or not m.data):return
 now=time.monotonic()
 if now-last_sent.get(kind,0)<{'cloud':.35,'image':.35,'odom':.2,'camera':.18}[kind]:return
 last_sent[kind]=now
 h=m.header;meta=dict(session_id=session_id,kind=kind,sec=h.stamp.secs,nsec=h.stamp.nsecs,frame=h.frame_id);data=b''
 if kind=='cloud':
  meta.update(height=m.height,width=m.width,fields=[[f.name,f.offset,f.datatype,f.count] for f in m.fields],is_bigendian=m.is_bigendian,point_step=m.point_step,row_step=m.row_step,is_dense=m.is_dense);data=bytes(m.data)
  if m.height==1 and m.width>48000:
   stride=(m.width+47999)//48000;a=np.frombuffer(data,dtype=np.uint8).reshape(m.width,m.point_step)[::stride];data=a.tobytes();meta.update(width=len(a),row_step=len(data))
 elif kind=='camera':
  meta.update(format=m.format);data=bytes(m.data)
 elif kind=='image':
  meta.update(height=m.height,width=m.width,encoding=m.encoding,is_bigendian=m.is_bigendian,step=m.step);data=bytes(m.data)
  if m.encoding=='bgr8':
   a=np.frombuffer(data,dtype=np.uint8).reshape(m.height,m.step)[:,:m.width*3].reshape(m.height,m.width,3)[::2,::2];data=a.tobytes();meta.update(height=a.shape[0],width=a.shape[1],step=a.shape[1]*3)
 else:
  p=m.pose.pose.position;q=m.pose.pose.orientation;meta['pose']=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]
 with lock:latest[kind]=(meta,data)
rospy.init_node('go2w_display_export')
subs=[rospy.Subscriber('/go2w_lio/cloud',PointCloud2,cb,'cloud',queue_size=1),rospy.Subscriber('/rgb_img',Image,cb,'image',queue_size=1),rospy.Subscriber('/go2w_livo/jpeg',CompressedImage,cb,'camera',queue_size=1,buff_size=4*1024*1024),rospy.Subscriber('/go2w_lio/odometry',Odometry,cb,'odom',queue_size=1)]
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',int(os.environ.get('GO2W_SOURCE_PORT','11325'))));s.listen(1);s.settimeout(1)
while not rospy.is_shutdown():
 try:c,_=s.accept()
 except socket.timeout:continue
 c.settimeout(2)
 try:
  while not rospy.is_shutdown():
   with lock:batch=list(latest.values());latest.clear()
   for meta,data in batch:
    h=json.dumps(meta).encode();c.sendall(struct.pack('!II',len(h),len(data))+h+data)
   time.sleep(.1)
 except (OSError,ConnectionError):pass
 finally:c.close()
