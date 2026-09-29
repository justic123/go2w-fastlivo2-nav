"""Restore board sensor epoch; reconnect same map only. No actuation."""
import json,socket,time,math
from pathlib import Path
import rospy
from nav_msgs.msg import Odometry
root=Path('/home/unitree/fast_livo2_port/build1')
expected=json.loads((root/'desktop_navigation.json').read_text())['session']
rospy.init_node('desktop_navigation_receive');pub=rospy.Publisher('/go2w_lio/odometry',Odometry,queue_size=2)
previous=None
while not rospy.is_shutdown():
 try:
  with socket.create_connection(('127.0.0.1',11337),timeout=3) as c:
   c.settimeout(2)
   with c.makefile('rb') as f:
    while not rospy.is_shutdown():
     line=f.readline(8193)
     if not line:raise ConnectionError('Desktop navigation connection closed')
     if len(line)>8192:raise RuntimeError('Invalid desktop pose packet')
     d=json.loads(line);v=d['pose'];stamp=float(d['stamp'])
     if d['session']!=expected or d['frame']!='camera_init':raise RuntimeError('Desktop map session/frame changed; explicit navigation restart required')
     if len(v)!=7 or not all(math.isfinite(x) for x in v+[stamp]):raise RuntimeError('Invalid pose')
     if not 0<=time.time()-stamp<.6:
      rospy.logwarn_throttle(1,'Discarding stale/future desktop pose age=%.3f'%(time.time()-stamp));continue
     if previous is not None:
      if stamp==previous:continue
      if stamp<previous:raise RuntimeError('Non-monotonic desktop pose')
     previous=stamp;m=Odometry();m.header.stamp=rospy.Time.from_sec(stamp);m.header.frame_id='camera_init';m.child_frame_id='body'
     m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z=v[:3]
     m.pose.pose.orientation.x,m.pose.pose.orientation.y,m.pose.pose.orientation.z,m.pose.pose.orientation.w=v[3:]
     pub.publish(m)
 except OSError as e:
  # Publish nothing during outages: existing age/watchdog checks stop goals.
  rospy.logwarn('Desktop pose disconnected; navigation input stale: %s'%e)
  time.sleep(.5)
