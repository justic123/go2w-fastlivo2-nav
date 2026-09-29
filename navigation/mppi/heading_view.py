"""Explicit body +X arrow. Lidar axes are deliberately not rendered as robot heading."""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from visualization_msgs.msg import Marker
rclpy.init();n=Node('mppi_body_heading');pub=n.create_publisher(Marker,'/mppi/body_heading',10)
def cb(odom):
 for ident,kind in ((0,Marker.ARROW),(1,Marker.TEXT_VIEW_FACING)):
  m=Marker();m.header.stamp=odom.header.stamp;m.header.frame_id='go2w_mppi_base';m.ns='body_forward';m.id=ident;m.type=kind;m.action=Marker.ADD;m.pose.orientation.w=1.;m.color.r=1.;m.color.g=.3;m.color.b=.05;m.color.a=1.;m.lifetime.nanosec=600000000
  if ident==0:m.pose.position.z=.25;m.scale.x=.65;m.scale.y=.09;m.scale.z=.13
  else:m.pose.position.z=.45;m.scale.z=.16;m.text='ROBOT FORWARD (+X)'
  pub.publish(m)
n.create_subscription(Odometry,'/mppi/odom',cb,10)
try:rclpy.spin(n)
except KeyboardInterrupt:pass
finally:n.destroy_node();rclpy.try_shutdown()
