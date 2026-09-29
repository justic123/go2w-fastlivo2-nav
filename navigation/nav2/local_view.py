#!/usr/bin/env python3
"""Laptop visualization only; no goal or velocity publishing."""
import json,socket,struct,threading,time,array,zlib
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid,Path
from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker
rclpy.init();node=Node('go2w_navigation_display');q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
mp=node.create_publisher(OccupancyGrid,'/go2w_nav_view/costmap',q);pp=node.create_publisher(Path,'/go2w_nav_view/plan',q);rp=node.create_publisher(Marker,'/go2w_view/robot_heading',10)
last_pose_stamp=None
def fused_heading(path):
 global last_pose_stamp
 if not path.poses:return
 p=path.poses[-1];stamp=p.header.stamp.sec+p.header.stamp.nanosec*1e-9
 previous=last_pose_stamp;last_pose_stamp=stamp
 if previous is None or stamp<=previous:return
 m=Marker();m.header=p.header;m.ns='current_fusion_heading';m.id=0;m.type=Marker.ARROW;m.action=Marker.ADD;m.pose=p.pose;m.scale.x=.65;m.scale.y=.08;m.scale.z=.12;m.color.r=1.;m.color.g=.82;m.color.a=1.;m.lifetime.sec=0;m.lifetime.nanosec=600000000;rp.publish(m)
node.create_subscription(Path,'/go2w_view/path',fused_heading,q)
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  a=c.recv(n-len(b))
  if not a:raise EOFError()
  b.extend(a)
 return bytes(b)
def loop():
 while rclpy.ok():
  try:
   with socket.create_connection(('127.0.0.1',11327),timeout=3) as c:
    c.settimeout(5)
    while rclpy.ok():
     n,size=struct.unpack('!II',exact(c,8))
     if n>2000000 or size>2000000:raise ValueError('oversize')
     d=json.loads(exact(c,n));raw=exact(c,size);kind=d['kind']
     if kind=='navmap':
      expected=d['width']*d['height']
      if not 0<expected<=8000000:raise ValueError('invalid map size')
      if d.get('encoding')=='zlib':raw=zlib.decompressobj().decompress(raw,expected+1)
      if len(raw)!=expected:raise ValueError('invalid map payload')
      m=OccupancyGrid();m.header.frame_id=d['frame'];m.header.stamp=node.get_clock().now().to_msg();m.info.width=d['width'];m.info.height=d['height'];m.info.resolution=d['resolution'];m.info.origin.position.x=d['x'];m.info.origin.position.y=d['y'];m.info.origin.orientation.w=1.;m.data=array.array('b',raw);mp.publish(m)
     elif kind=='navpath':
      m=Path();m.header.frame_id=d['frame'];m.header.stamp=node.get_clock().now().to_msg()
      for v in d['points']:
       p=PoseStamped();p.header=m.header;p.pose.position.x,p.pose.position.y,p.pose.position.z=v;p.pose.orientation.w=1.;m.poses.append(p)
      pp.publish(m)
     elif kind=='robot':
      pass # Legacy navigation pose may belong to a stopped/different session. Use current fusion path only.
  except (OSError,EOFError,ValueError):time.sleep(1)
threading.Thread(target=loop,daemon=True).start()
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.shutdown()
