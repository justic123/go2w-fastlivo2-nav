#!/usr/bin/env python3
"""Publish one saved map and trajectory on isolated display-only topics."""
import sys
from pathlib import Path
import numpy as np
import rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import PointCloud2,PointField
from nav_msgs.msg import Path as NavPath
from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker,MarkerArray
root=Path(sys.argv[1]);raw=(root/'map_xyz_10cm.pcd').read_bytes().split(b'DATA binary\n',1)[1]
assert len(raw)%12==0
rows=np.loadtxt(root/'trajectory.tum',ndmin=2);assert rows.shape[1]==8 and np.isfinite(rows).all()
rclpy.init();node=rclpy.create_node('go2w_saved_map_display');q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
cp=node.create_publisher(PointCloud2,'/go2w_saved/cloud',q);pp=node.create_publisher(NavPath,'/go2w_saved/path',q);mp=node.create_publisher(MarkerArray,'/go2w_saved/markers',q)
c=PointCloud2();c.header.frame_id='camera_init';c.height=1;c.width=len(raw)//12;c.point_step=12;c.row_step=len(raw);c.is_dense=True;c.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(['x','y','z'])];c.data=raw
path=NavPath();path.header.frame_id='camera_init'
for row in rows:
 p=PoseStamped();p.header.frame_id='camera_init';p.pose.position.x,p.pose.position.y,p.pose.position.z=map(float,row[1:4]);p.pose.orientation.x,p.pose.orientation.y,p.pose.orientation.z,p.pose.orientation.w=map(float,row[4:]);path.poses.append(p)
marks=MarkerArray()
for i,(label,row,color) in enumerate([('Start',rows[0],(0.,1.,.2)),('End',rows[-1],(1.,.3,.1))]):
 for kind in ('sphere','label'):
  m=Marker();m.header.frame_id='camera_init';m.ns=kind;m.id=i;m.action=Marker.ADD;m.type=Marker.SPHERE if kind=='sphere' else Marker.TEXT_VIEW_FACING;m.pose.orientation.w=1.;m.pose.position.x,m.pose.position.y,m.pose.position.z=map(float,row[1:4]);m.color.r,m.color.g,m.color.b=color;m.color.a=1.
  if kind=='sphere':m.scale.x=m.scale.y=m.scale.z=.10
  else:m.text=label;m.scale.z=.16;m.pose.position.z+=.25+i*.2
  marks.markers.append(m)
def publish():
 stamp=node.get_clock().now().to_msg();c.header.stamp=stamp;path.header.stamp=stamp
 for p in path.poses:p.header.stamp=stamp
 for m in marks.markers:m.header.stamp=stamp
 cp.publish(c);pp.publish(path);mp.publish(marks)
node.create_timer(1.,publish);publish();print(f'Saved map: {c.width} points, {len(rows)} poses; {root}',flush=True)
try:rclpy.spin(node)
except KeyboardInterrupt:pass
finally:node.destroy_node();rclpy.shutdown()
