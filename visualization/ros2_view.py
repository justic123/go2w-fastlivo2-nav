#!/usr/bin/env python3
import json,socket,struct,threading,time,sys,os
from pathlib import Path
import io
from PIL import Image as PillowImage
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import PointCloud2,PointField,Image
from nav_msgs.msg import Path as NavPath
from geometry_msgs.msg import PoseStamped
from display_map import DisplayMap
from display_session import DisplaySession
rclpy.init();node=Node('go2w_display_import');q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
cp=node.create_publisher(PointCloud2,'/go2w_view/cloud',q);ip=node.create_publisher(Image,'/go2w_view/image',10);pp=node.create_publisher(NavPath,'/go2w_view/path',q)
display_map=DisplayMap();map_frame=None
camera_pub=node.create_publisher(Image,'/go2w_view/camera',10)
path=NavPath();counts={'cloud':0,'image':0,'odom':0,'camera':0};status=Path(os.environ.get('GO2W_VIEW_STATE_DIR',str(Path(__file__).parent)))/'view_status.json'
session=DisplaySession();connections=0;resets=0;last_reset=None
events=status.with_name('view_events.jsonl')
def event(kind,**details):
 with events.open('a') as f:f.write(json.dumps(dict(event=kind,local_time=time.time(),**details))+'\n')
def header(h,m):h.frame_id=m['frame'] or 'camera_init';h.stamp.sec=m['sec'];h.stamp.nanosec=m['nsec']
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  a=c.recv(n-len(b))
  if not a:raise EOFError()
  b.extend(a)
 return bytes(b)
def loop():
 global display_map,map_frame,connections,resets,last_reset
 while rclpy.ok():
  try:
   with socket.create_connection(('127.0.0.1',int(os.environ.get('GO2W_VIEW_PORT','11325'))),timeout=2) as c:
    connections+=1;event('connected',connection=connections)
    c.settimeout(10)
    while rclpy.ok():
     n,size=struct.unpack('!II',exact(c,8))
     if n>16384 or size>16000000:raise ValueError('Oversized display packet')
     m=json.loads(exact(c,n));data=exact(c,size);kind=m['kind']
     reset=session.observe(m,connections)
     if reset:
      path.poses.clear();display_map=DisplayMap();map_frame=None;resets+=1;last_reset=reset
      event('display_reset',reason=reset,session=m.get('session_id'))
      # Clear latched old displays immediately, including if the first packet is an image.
      empty=PointCloud2();empty.header.frame_id='camera_init';empty.height=1;empty.width=0;empty.point_step=16;empty.fields=[PointField(name=k,offset=i*4,datatype=7 if i<3 else 6,count=1) for i,k in enumerate(['x','y','z','rgb'])];cp.publish(empty)
      path.header.frame_id='camera_init';pp.publish(path)
     if kind=='cloud':
      if not m['width'] or not m['height'] or not data:continue
      if map_frame is not None and m['frame']!=map_frame:raise ValueError('Display map frame changed')
      if not display_map.add(m,data):continue
      map_frame=m['frame'];raw,npoints=display_map.packed()
      out=PointCloud2();header(out.header,m);out.height=1;out.width=npoints;out.is_bigendian=False;out.point_step=16;out.row_step=npoints*16;out.is_dense=True
      out.fields=[PointField(name=k,offset=i*4,datatype=7 if i<3 else 6,count=1) for i,k in enumerate(['x','y','z','rgb'])];out.data=raw;cp.publish(out)
     elif kind=='camera':
      with PillowImage.open(io.BytesIO(data)) as im:decoded=im.convert('RGB').resize((640,360),PillowImage.BILINEAR)
      out=Image();header(out.header,m);out.height=360;out.width=640;out.encoding='rgb8';out.step=1920;out.data=decoded.tobytes();camera_pub.publish(out)
     elif kind=='image':
      out=Image();header(out.header,m)
      for k in ['height','width','encoding','is_bigendian','step']:setattr(out,k,m[k])
      out.data=data;ip.publish(out)
     elif kind=='odom':
      p=PoseStamped();header(p.header,m);v=m['pose'];p.pose.position.x,p.pose.position.y,p.pose.position.z=v[:3];p.pose.orientation.x,p.pose.orientation.y,p.pose.orientation.z,p.pose.orientation.w=v[3:];path.header=p.header;path.poses.append(p);path.poses=path.poses[-5000:];pp.publish(path)
     counts[kind]+=1;status.write_text(json.dumps(dict(connections=connections,display_resets=resets,last_reset_reason=last_reset,session_id=m.get("session_id"),counts=counts,map_points=len(display_map.points),map_capped=display_map.capped,display_voxel_m=display_map.voxel,coarsenings=display_map.coarsenings,last_received_local=time.time())))
  except (OSError,EOFError,ValueError) as e:
   event('disconnected',reason=str(e),retained_map_points=len(display_map.points));time.sleep(1)
if len(sys.argv)>1:
 raw=Path(sys.argv[1]).read_bytes().split(b'DATA binary\n',1)[1];m=PointCloud2();m.header.frame_id='camera_init';m.height=1;m.width=len(raw)//12;m.point_step=12;m.row_step=len(raw);m.is_dense=True;m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(['x','y','z'])];m.data=raw;cp.publish(m)
threading.Thread(target=loop,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.shutdown()
