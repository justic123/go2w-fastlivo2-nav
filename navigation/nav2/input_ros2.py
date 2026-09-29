#!/usr/bin/env python3
"""Board-only navigation input + read-only visualization export. No SportClient/cmd_vel output."""
import json,time,struct,socket,threading,os,zlib
import numpy as np
from pathlib import Path
from odom_twist import planar_twist
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry,OccupancyGrid,Path as NavPath
from sensor_msgs.msg import PointCloud2,PointField
from geometry_msgs.msg import TransformStamped,Twist
from tf2_ros import TransformBroadcaster,StaticTransformBroadcaster
root=Path('/dev/shm/go2w_nav');last={};latest={};lock=threading.Lock()
rclpy.init();node=Node('go2w_nav_adapter_readonly');tf=TransformBroadcaster(node);static=StaticTransformBroadcaster(node)
op=node.create_publisher(Odometry,'/go2w_nav/odom',10);cp=node.create_publisher(PointCloud2,'/go2w_nav/cloud',5)
def stamp(t):
 from builtin_interfaces.msg import Time
 sec=int(t);return Time(sec=sec,nanosec=int((t-sec)*1e9))
def put(kind,meta,data=b''):
 with lock:latest[kind]=(dict(meta,kind=kind),data)
def grid(m):put('navmap',dict(frame=m.header.frame_id,width=m.info.width,height=m.info.height,resolution=m.info.resolution,x=m.info.origin.position.x,y=m.info.origin.position.y,encoding='zlib'),zlib.compress(np.asarray(m.data,dtype=np.int8).tobytes(),1))
def path(m):put('navpath',dict(frame=m.header.frame_id,points=[[p.pose.position.x,p.pose.position.y,p.pose.position.z] for p in m.poses]))
node.create_subscription(OccupancyGrid,'/global_costmap/costmap',grid,10)
node.create_subscription(NavPath,'/plan',path,10)
node.create_subscription(Twist,'/go2w_nav/proposed_cmd_vel',lambda m:put('command',dict(vx=m.linear.x,w=m.angular.z,actuation_enabled=False)),10)
static_sent=False;pose_stamp=None;cloud_stamp=None;previous=None
status=dict(actuation_enabled=False,pose_count=0,cloud_count=0)
def tick():
 global static_sent,pose_stamp,cloud_stamp,previous
 try:
  if not static_sent:
   e=json.loads((root/'extrinsic.json').read_text());m=TransformStamped();m.header.frame_id='go2w_base';m.child_frame_id='go2w_lidar';m.header.stamp=node.get_clock().now().to_msg();m.transform.translation.x,m.transform.translation.y,m.transform.translation.z=map(float,e['t']);m.transform.rotation.x,m.transform.rotation.y,m.transform.rotation.z,m.transform.rotation.w=e['q'];static.sendTransform(m);static_sent=True
  for name in ['pose.json','cloud.bin']:
   p=root/name;mt=p.stat().st_mtime_ns
   if last.get(name)==mt:continue
   data=p.read_bytes();last[name]=mt
   if name=='pose.json':
    snapshot=json.loads(data)
    for d in snapshot.get('history',[snapshot]):
     if pose_stamp is not None and d['stamp']<=pose_stamp:continue  # Atomic file replacement may be observed twice.
     if not 0<=time.time()-d['receipt']<.85:continue
     v=d['pose'];m=Odometry();m.header.stamp=stamp(d['stamp']);m.header.frame_id='camera_init';m.child_frame_id='go2w_base';m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z=v[:3];m.pose.pose.orientation.x,m.pose.pose.orientation.y,m.pose.pose.orientation.z,m.pose.pose.orientation.w=v[3:]
     # Twist is an estimate from odometry differences, not commanded velocity.
     if previous:
      import math
      dt=d['stamp']-previous['stamp']
      if dt>0:
       m.twist.twist.linear.x,m.twist.twist.linear.y,m.twist.twist.angular.z=planar_twist(previous,d)
     previous=d;op.publish(m);t=TransformStamped();t.header=m.header;t.child_frame_id=m.child_frame_id;t.transform.translation.x,t.transform.translation.y,t.transform.translation.z=v[:3];t.transform.rotation=m.pose.pose.orientation;tf.sendTransform(t);pose_stamp=d['stamp'];status['pose_count']+=1;put('robot',dict(frame='camera_init',pose=v))
   else:
    n=struct.unpack('!I',data[:4])[0];d=json.loads(data[4:4+n]);raw=data[4+n:]
    if not 0<=time.time()-d['receipt']<.8 or len(raw)!=d['n']*12:continue
    m=PointCloud2();m.header.stamp=stamp(d['stamp']);m.header.frame_id='go2w_lidar';m.height=1;m.width=d['n'];m.point_step=12;m.row_step=len(raw);m.is_dense=True;m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(['x','y','z'])];m.data=raw;cp.publish(m);cloud_stamp=d['stamp'];status['cloud_count']+=1
  status['pose_age_s']=time.time()-pose_stamp if pose_stamp is not None else None;status['cloud_age_s']=time.time()-cloud_stamp if cloud_stamp is not None else None;status['last_check']=time.time();status['latest_pose_stamp']=pose_stamp;(root/'adapter_status.tmp').write_text(json.dumps(status));os.replace(str(root/'adapter_status.tmp'),str(root/'adapter_status.json'))
 except (FileNotFoundError,ValueError,KeyError) as e:node.get_logger().warn(str(e))
def server():
 s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',11327));s.listen(1);s.settimeout(1)
 while rclpy.ok():
  try:c,_=s.accept()
  except socket.timeout:continue
  c.settimeout(2)
  sent={}
  try:
   while rclpy.ok():
    with lock:batch=sorted(latest.items(),key=lambda item:0 if item[0]=='robot' else 1)
    for kind,item in batch:
     if sent.get(kind) is item:continue
     meta,data=item
     h=json.dumps(meta).encode();c.sendall(struct.pack('!II',len(h),len(data))+h+data);sent[kind]=item
    time.sleep(.1)
  except OSError:pass
  finally:c.close()
node.create_timer(.05,tick);threading.Thread(target=server,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.shutdown()
