"""Read-only native ROS1 JPEG subscription; no additional SDK video client."""
import time
import rospy
from sensor_msgs.msg import CompressedImage,PointCloud2
from common import ROOT,CACHE,atomic,read
from rgb_cloud import Accumulator,decode
import threading
import numpy as np
pending=None;rgb_lock=threading.Lock();rgb_session=None;rgb_acc=Accumulator();rgb_started=0.;rgb_mapping=False
def rgb_callback(m):
    global pending
    if m.width and m.header.frame_id=="camera_init":
        with rgb_lock:pending=m
def rgb_tick(_):
    global pending,rgb_session,rgb_acc,rgb_started,rgb_mapping
    with rgb_lock:m=pending;pending=None
    if m is None:return
    session=read(ROOT/"board/current.json").get("run")
    if not session:return
    d=read(ROOT/"demo/state.json")
    if session!=rgb_session:
        rgb_session=session;rgb_acc=Accumulator();rgb_started=time.time();rgb_mapping=d.get("phase")=="mapping"
        # A web-only restart must not clear an ongoing mapping display.
        cached=read(CACHE/'native-rgb.json')
        if cached.get('session')==session and cached.get('frame')=='camera_init' and 0<cached.get('count',0)<=400000:
            try:
                saved=np.fromfile(CACHE/'native-rgb.bin',dtype='<f4').reshape(-1,6)
                if len(saved)==cached['count'] and np.isfinite(saved).all():
                    rgb_acc.voxel=max(.02,float(cached.get('voxel_m',.02)));rgb_acc.add(saved);rgb_started=cached['started'];rgb_mapping=cached.get('from_mapping',False)
            except (OSError,ValueError,KeyError):pass
    if d.get("phase")=="mapping" and d.get("session")==session:rgb_mapping=True
    try:
        a=decode(m);rgb_acc.add(a);a=rgb_acc.array()
        atomic(CACHE/"native-rgb.bin",a.tobytes())
        atomic(CACHE/"native-rgb.json",dict(updated=time.time(),session=session,frame="camera_init",count=len(a),voxel_m=rgb_acc.voxel,format="xyzrgb-f32",started=rgb_started,from_mapping=rgb_mapping,stamp=m.header.stamp.to_sec()))
    except Exception as e:rospy.logwarn_throttle(10,"RGB display: %s",str(e))
last=0.
def callback(m):
    global last
    now=time.monotonic()
    if now-last<.45:return
    if not bytes(m.data).startswith(b'\xff\xd8'):return
    last=now;atomic(CACHE/'camera.jpg',bytes(m.data));atomic(CACHE/'camera.json',dict(updated=time.time(),stamp=m.header.stamp.to_sec(),source='/go2w_livo/jpeg'))
rospy.init_node('go2w_web_camera',disable_signals=False)
rospy.Subscriber('/go2w_livo/jpeg',CompressedImage,callback,queue_size=1,buff_size=4*1024*1024)
rospy.Subscriber('/go2w_lio/cloud',PointCloud2,rgb_callback,queue_size=1,buff_size=4*1024*1024)
rospy.Timer(rospy.Duration(1.),rgb_tick)
rospy.spin()
