#!/usr/bin/env python3
import queue,json,socket,struct,threading,time,sys,os
from pathlib import Path
import io
from PIL import Image as PillowImage
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import PointCloud2,PointField,Image
from nav_msgs.msg import Path as NavPath
from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'visualization'))
from display_map import DisplayMap
from display_session import DisplaySession
rclpy.init();node=Node('go2w_display_import');q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
cp=node.create_publisher(PointCloud2,'/go2w_view/cloud',q);ip=node.create_publisher(Image,'/go2w_view/image',10);pp=node.create_publisher(NavPath,'/go2w_view/path',q)
display_map=DisplayMap();map_frame=None
camera_pub=node.create_publisher(Image,'/go2w_view/camera',10)
path=NavPath();counts={'cloud':0,'image':0,'odom':0,'camera':0};status=Path(os.environ.get('GO2W_VIEW_STATE_DIR',str(Path(__file__).parent)))/'view_status.json'
session=DisplaySession();connections=0;resets=0;last_reset=None
events=status.with_name('view_events.jsonl')
cloud_queue=queue.Queue(maxsize=1);map_lock=threading.Lock()
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

def render_cloud(m,data):
 global map_frame
 with map_lock:
  if not m['width'] or not m['height'] or not data:return
  if map_frame is not None and m['frame']!=map_frame:raise ValueError('Display map frame changed')
  if not display_map.add(m,data):return
  map_frame=m['frame'];raw,npoints=display_map.packed()
  out=PointCloud2();header(out.header,m);out.height=1;out.width=npoints;out.is_bigendian=False;out.point_step=16;out.row_step=npoints*16;out.is_dense=True
  out.fields=[PointField(name=k,offset=i*4,datatype=7 if i<3 else 6,count=1) for i,k in enumerate(['x','y','z','rgb'])];out.data=raw;cp.publish(out)
def cloud_worker():
 while rclpy.ok():
  try:m,data=cloud_queue.get(timeout=.5)
  except queue.Empty:continue
  try:render_cloud(m,data)
  except (ValueError,RuntimeError) as e:event('cloud_render_error',reason=str(e))

pending={};pending_lock=threading.Lock()
def restore_snapshot(m):
 global display_map,map_frame
 if session.identity != ('session',m.get('session_id')):return
 try:
  import numpy as np
  root=Path(__file__).parent;meta=json.loads((root/'display_snapshot.json').read_text())
  if m.get('session_id')!=meta['session_id'] or meta['point_step']!=16:return
  data=np.frombuffer((root/'display_snapshot.bin').read_bytes(),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')])
  restored=DisplayMap(voxel=meta['voxel']);xyz=np.column_stack([data[k] for k in ['x','y','z']]);keys=np.floor(xyz/restored.voxel).astype('int64')
  restored.points={tuple(k):(float(v['x']),float(v['y']),float(v['z']),int(v['rgb'])) for k,v in zip(keys,data)}
  with map_lock:display_map=restored;map_frame=m['frame'] or 'camera_init'
  event('snapshot_restored',points=len(restored.points))
 except (OSError,ValueError,KeyError) as e:event('snapshot_not_restored',reason=str(e))
def receive():
 global connections
 while rclpy.ok():
  try:
   with socket.create_connection(('127.0.0.1',int(os.environ.get('GO2W_VIEW_PORT','11325'))),timeout=2) as c:
    connections+=1;event('connected',connection=connections);c.settimeout(10)
    while rclpy.ok():
     n,size=struct.unpack('!II',exact(c,8))
     if n>16384 or size>16000000:raise ValueError('Oversized display packet')
     m=json.loads(exact(c,n));data=exact(c,size)
     with pending_lock:pending[m['kind']]=(m,data,connections,time.monotonic())
  except (OSError,EOFError,ValueError) as e:
   event('disconnected',reason=str(e));time.sleep(1)
def loop():
 global display_map,map_frame,resets,last_reset
 while rclpy.ok():
  with pending_lock:batch=sorted(pending.values(),key=lambda item:0 if item[0]['kind']=='odom' else 1);pending.clear()
  for m,data,connection,received in batch:
   try:
    kind=m['kind']
    reset=session.observe(m,connection)
    if reset:
     path.poses.clear()
     with map_lock:display_map=DisplayMap();map_frame=None
     resets+=1;last_reset=reset
     event('display_reset',reason=reset,session=m.get('session_id'))
     restore_snapshot(m)
     # Clear latched old displays immediately, including if the first packet is an image.
     empty=PointCloud2();empty.header.frame_id='camera_init';empty.height=1;empty.width=0;empty.point_step=16;empty.fields=[PointField(name=k,offset=i*4,datatype=7 if i<3 else 6,count=1) for i,k in enumerate(['x','y','z','rgb'])];
     if not display_map.points:cp.publish(empty)
     path.header.frame_id='camera_init';pp.publish(path)
    if kind=='cloud':
     try:cloud_queue.put_nowait((m,data))
     except queue.Full:
      try:cloud_queue.get_nowait()
      except queue.Empty:pass
      cloud_queue.put_nowait((m,data))
    elif kind=='camera':
     with PillowImage.open(io.BytesIO(data)) as im:decoded=im.convert('RGB').resize((640,360),PillowImage.BILINEAR)
     out=Image();header(out.header,m);out.height=360;out.width=640;out.encoding='rgb8';out.step=1920;out.data=decoded.tobytes();camera_pub.publish(out)
    elif kind=='image':
     out=Image();header(out.header,m)
     for k in ['height','width','encoding','is_bigendian','step']:setattr(out,k,m[k])
     out.data=data;ip.publish(out)
    elif kind=='odom':
     p=PoseStamped();header(p.header,m);v=m['pose'];p.pose.position.x,p.pose.position.y,p.pose.position.z=v[:3];p.pose.orientation.x,p.pose.orientation.y,p.pose.orientation.z,p.pose.orientation.w=v[3:];path.header=p.header;path.poses.append(p);path.poses=path.poses[-5000:];pp.publish(path)
    counts[kind]+=1;temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps(dict(connections=connections,display_resets=resets,last_reset_reason=last_reset,session_id=m.get("session_id"),counts=counts,map_points=len(display_map.points),map_capped=display_map.capped,display_voxel_m=display_map.voxel,coarsenings=display_map.coarsenings,last_received_local=time.time(),display_receive_age_s=time.monotonic()-received)))
    temporary.replace(status)
   except (OSError,ValueError,KeyError) as e:event('display_packet_error',reason=str(e))
  time.sleep(.01)
# Show stale mapping explicitly instead of leaving an apparently live frozen map.
health_pub=node.create_publisher(Marker,'/go2w_view/status',q)
def health_marker():
 m=Marker();m.header.frame_id='camera_init';m.ns='mapping_health';m.id=0;m.type=Marker.TEXT_VIEW_FACING;m.action=Marker.ADD;m.pose.orientation.w=1.;m.pose.position.z=1.2;m.scale.z=.15;m.color.a=1.
 if path.poses:
  m.pose.position.x=path.poses[-1].pose.position.x;m.pose.position.y=path.poses[-1].pose.position.y
 try:
  current=json.loads((Path(__file__).parent/'current.json').read_text());h=json.loads((Path(current['folder'])/'health.json').read_text());age=time.time()-h['updated']
  live=age<2 and h.get('ready',False)
  m.text=('LIVE - lag %.2fs'%h['lag_last_s']) if live else ('STALE - mapping stopped' if age>=2 else 'DELAYED - do not navigate')
  m.color.g=1. if live else .15;m.color.r=.15 if live else 1.
 except (OSError,ValueError,KeyError,TypeError):m.text='WAITING FOR MAPPING';m.color.r=1.
 health_pub.publish(m)
node.create_timer(.5,health_marker)
if len(sys.argv)>1:
 raw=Path(sys.argv[1]).read_bytes().split(b'DATA binary\n',1)[1];m=PointCloud2();m.header.frame_id='camera_init';m.height=1;m.width=len(raw)//12;m.point_step=12;m.row_step=len(raw);m.is_dense=True;m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(['x','y','z'])];m.data=raw;cp.publish(m)
threading.Thread(target=cloud_worker,daemon=True).start()
threading.Thread(target=receive,daemon=True).start()
threading.Thread(target=loop,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.shutdown()
