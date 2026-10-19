"""Publish the onboard ROS1 wall clock to downstream isolated Nav2, without retiming sensors."""
import rospy
from rosgraph_msgs.msg import Clock

rospy.init_node('onboard_clock_source')
if rospy.get_param('/use_sim_time', False):
    raise RuntimeError('Native onboard acquisition must use wall time')
pub = rospy.Publisher('/clock', Clock, queue_size=2)
rate = rospy.Rate(50)
while not rospy.is_shutdown():
    pub.publish(Clock(clock=rospy.Time.now()))
    rate.sleep()
