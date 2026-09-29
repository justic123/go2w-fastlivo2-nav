"""Read-only ROS1 export for MPPI. Original clock/stamps; no SDK, no control subscription."""
import json, socket, struct, threading, time, os
import rospy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from rosgraph_msgs.msg import Clock
rospy.init_node('mppi_input_export', anonymous=False)
latest = {}; lock = threading.Lock()
session = os.environ['GO2W_MPPI_SESSION']
def callback(m, kind):
    stamp = m.clock.to_sec() if kind == 'clock' else m.header.stamp.to_sec()
    d = dict(kind=kind, stamp=stamp, session=session)
    raw = b''
    if kind == 'odom':
        p=m.pose.pose.position; q=m.pose.pose.orientation
        d.update(frame=m.header.frame_id, pose=[p.x,p.y,p.z,q.x,q.y,q.z,q.w])
    elif kind == 'cloud':
        d.update(frame=m.header.frame_id, width=m.width, height=m.height,
                 point_step=m.point_step, row_step=m.row_step, bigendian=m.is_bigendian,
                 fields=[[f.name,f.offset,f.datatype,f.count] for f in m.fields])
        raw=bytes(m.data)
    with lock: latest[kind]=(d,raw,time.monotonic())
rospy.Subscriber('/clock',Clock,callback,'clock',queue_size=1)
rospy.Subscriber('/go2w_lio/odometry',Odometry,callback,'odom',queue_size=1)
rospy.Subscriber('/go2w_lio/points',PointCloud2,callback,'cloud',queue_size=1,buff_size=16000000)
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('127.0.0.1',11339));s.listen(1);s.settimeout(1)
while not rospy.is_shutdown():
    try:c,_=s.accept()
    except socket.timeout:continue
    sent={};c.settimeout(.5)
    try:
        while not rospy.is_shutdown():
            with lock: batch=[(k,latest[k]) for k in ('clock','odom','cloud') if k in latest]
            for k,item in batch:
                if sent.get(k) is item or time.monotonic()-item[2]>.3:continue
                h=json.dumps(item[0]).encode();c.sendall(struct.pack('!II',len(h),len(item[1]))+h+item[1]);sent[k]=item
            time.sleep(.005)
    except OSError:pass
    finally:c.close()
