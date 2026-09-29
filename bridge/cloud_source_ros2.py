#!/usr/bin/env python3
"""Subscribe XT16 only, forward unchanged payload over a private local socket."""
import json,socket,struct,sys,time
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy,DurabilityPolicy
from sensor_msgs.msg import PointCloud2
sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.connect(sys.argv[1]);sock.settimeout(2)
rclpy.init();node=rclpy.create_node('xt16_input_bridge_source')
def callback(m):
 meta=dict(stamp_sec=m.header.stamp.sec,stamp_nanosec=m.header.stamp.nanosec,width=m.width,height=m.height,point_step=m.point_step,row_step=m.row_step,bigendian=m.is_bigendian,fields=[[f.name,f.datatype,f.offset,f.count] for f in m.fields],size=len(m.data),receipt=time.time())
 hdr=json.dumps(meta).encode();sock.sendall(struct.pack('!I',len(hdr))+hdr+bytes(m.data))
sub=node.create_subscription(PointCloud2,'/unitree/slam_lidar/points',callback,QoSProfile(depth=3,reliability=ReliabilityPolicy.BEST_EFFORT,durability=DurabilityPolicy.VOLATILE))
try:rclpy.spin(node)
except (BrokenPipeError,ConnectionResetError):pass
finally:node.destroy_node();rclpy.shutdown();sock.close()
