#!/usr/bin/env python3
"""Diagnostic only: incoming stamp is SDK RESPONSE time, not exposure time."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np,rospy
from sensor_msgs.msg import CompressedImage,Image
rospy.init_node('go2w_livo_image_decode')
out=Path(sys.argv[1]);pub=rospy.Publisher('/go2w_livo/image_raw',Image,queue_size=2)
s=dict(received=0,published=0,rejected=0,stamp_source='SDK response receipt; uncalibrated',input_size=[1920,1080],output_size=[640,360])
def cb(msg):
 s['received']+=1
 try:
  a=cv2.imdecode(np.frombuffer(msg.data,dtype=np.uint8),cv2.IMREAD_COLOR)
  if a is None or a.shape!=(1080,1920,3):raise ValueError('Expected raw 1920x1080 RGB JPEG')
  a=cv2.resize(a,(640,360),interpolation=cv2.INTER_AREA)
  m=Image();m.header=msg.header;m.height=360;m.width=640;m.encoding='bgr8';m.is_bigendian=False;m.step=1920;m.data=a.tobytes()
  pub.publish(m);s['published']+=1
 except Exception as e:s['rejected']+=1;rospy.logerr(str(e))
sub=rospy.Subscriber('/go2w_livo/jpeg',CompressedImage,cb,queue_size=2,buff_size=4*1024*1024)
try:
 end=time.monotonic()+95
 while not rospy.is_shutdown() and time.monotonic()<end:rospy.sleep(.1)
finally:
 sub.unregister();out.write_text(json.dumps(s,indent=2)+'\n')
