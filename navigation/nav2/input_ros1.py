#!/usr/bin/env python3
"""板内只读 ROS1→ROS2 输入快照；不依赖笔记本、不包含运控接口。"""
import json,os,time,threading
from collections import deque
from imu_snapshot import select_snapshot
from pathlib import Path
import numpy as np,rospy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2,Imu
from tf.transformations import quaternion_from_matrix
root=Path('/dev/shm/go2w_nav');root.mkdir(exist_ok=True)
def atomic(name,data):
 p=root/name;tmp=p.with_suffix('.tmp');tmp.write_bytes(data);os.replace(str(tmp),str(p))
rospy.init_node('go2w_nav_input_readonly')
R=np.array(rospy.get_param('/go2w_lio/extrin_calib/extrinsic_R')).reshape(3,3);T=rospy.get_param('/go2w_lio/extrin_calib/extrinsic_T');M=np.eye(4);M[:3,:3]=R
atomic('extrinsic.json',json.dumps(dict(t=T,q=quaternion_from_matrix(M).tolist(),candidate=True)).encode())
pose_history=deque(maxlen=32)
last=0.
def pose(m):
 p=m.pose.pose.position;q=m.pose.pose.orientation
 if m.header.frame_id!='camera_init':return
 vals=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]
 if not np.isfinite(vals).all():return
 d=dict(stamp=m.header.stamp.to_sec(),receipt=time.time(),pose=vals);pose_history.append(d)
 atomic('pose.json',json.dumps(dict(d,history=list(pose_history))).encode())
def cloud(m):
 global last
 now=time.monotonic()
 if now-last<.18:return
 last=now
 fs={f.name:f for f in m.fields}
 if any(fs[k].datatype!=7 for k in ('x','y','z')):return
 endian='>' if m.is_bigendian else '<'
 dt=np.dtype(dict(names=['x','y','z'],formats=[endian+'f4']*3,offsets=[fs[k].offset for k in ['x','y','z']],itemsize=m.point_step))
 a=np.ndarray((m.height,m.width),dtype=dt,buffer=m.data,strides=(m.row_step,m.point_step));xyz=np.column_stack([a[k].ravel() for k in ['x','y','z']]);xyz=xyz[np.isfinite(xyz).all(1)]
 if len(xyz)<500:return
 # Navigation uses all viewing directions, independent of the RGB-visible subset.
 _,i=np.unique(np.floor(xyz/.1).astype(np.int32),axis=0,return_index=True);xyz=xyz[i].astype('<f4')
 meta=json.dumps(dict(stamp=m.header.stamp.to_sec(),receipt=time.time(),n=len(xyz))).encode()
 import struct
 atomic('cloud.bin',struct.pack('!I',len(meta))+meta+xyz.tobytes())
imu_previous=None;imu_fault=None;imu_latest=None
imu_records=deque(maxlen=750);imu_samples=deque(maxlen=750);imu_lock=threading.Lock()
def imu(m):
 global imu_previous,imu_fault,imu_latest
 stamp=m.header.stamp.to_sec();now=time.monotonic()
 if imu_previous is not None and (stamp<=imu_previous or stamp-imu_previous>.020001):imu_fault='IMU timestamp discontinuity'
 imu_previous=stamp
 with imu_lock:
  imu_latest=dict(stamp=stamp,receipt=time.time(),fault=imu_fault)
  imu_records.append(dict(imu_latest))
  imu_samples.append([stamp,m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z])
def write_imu_health(_):
 # Snapshot the latest sample, not the first sample of a burst. Receipt is not refreshed.
 with imu_lock:data=select_snapshot(imu_records,imu_samples,time.time(),imu_fault)
 if data is not None:atomic('imu_health.json',json.dumps(data).encode())
imu_timer=rospy.Timer(rospy.Duration(.05),write_imu_health)
rospy.Subscriber('/go2w_lio/imu',Imu,imu,queue_size=2000)
rospy.Subscriber('/go2w_lio/odometry' ,Odometry,pose,queue_size=64)
rospy.Subscriber('/go2w_lio/points',PointCloud2,cloud,queue_size=1,buff_size=8*1024*1024)
rospy.spin()
