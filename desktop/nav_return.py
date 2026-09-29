"""Read-only desktop odometry return; board validates source time and session."""
import json,socket,threading,time,sys
from pathlib import Path
from collections import deque
import rospy
from nav_msgs.msg import Odometry
folder=Path(sys.argv[1]);session=folder.name
rospy.init_node('desktop_navigation_return');latest=None;lock=threading.Lock();pending=deque();overflow=False;connected=False
def cb(m):
 global latest,overflow
 p=m.pose.pose.position;q=m.pose.pose.orientation
 offset=json.loads((folder/'transport.json').read_text())['clock_offset']
 d=dict(session=session,stamp=m.header.stamp.to_sec()-offset,frame=m.header.frame_id,pose=[p.x,p.y,p.z,q.x,q.y,q.z,q.w])
 with lock:
  if not connected:pending.clear()
  if len(pending)>=128:overflow=True
  else:pending.append((time.monotonic(),d))
rospy.Subscriber('/go2w_lio/odometry',Odometry,cb,queue_size=128)
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',11337));s.listen(1);s.settimeout(1)
while not rospy.is_shutdown():
 try:c,_=s.accept()
 except socket.timeout:continue
 c.settimeout(1);last=None
 with lock:connected=True
 try:
  while not rospy.is_shutdown():
   with lock:
    if overflow:raise RuntimeError('Pose return queue overflow; navigation must stop')
    item=pending.popleft() if pending else None
   if item and time.monotonic()-item[0]<.5 and item[1]['stamp']!=last:
    c.sendall(json.dumps(item[1]).encode()+b'\n');last=item[1]['stamp']
   time.sleep(.002)
 except OSError:pass
 finally:
  with lock:connected=False;pending.clear()
  c.close()
