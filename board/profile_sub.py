#!/usr/bin/env python3
"""Read-only replay observer; records source and wall clocks separately."""
import json
import sys
import threading
import time
import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Float64

rospy.init_node('board_profile_observer')
lock = threading.Lock()
with open(sys.argv[1], 'x', buffering=1) as output:
    def emit(kind, data):
        with lock:
            output.write(json.dumps(dict(kind=kind, wall=time.monotonic(), data=data), allow_nan=False)+'\n')
    def profile(message):
        emit('profile', json.loads(message.data))
    def odometry(message):
        p=message.pose.pose.position; q=message.pose.pose.orientation
        emit('odom', dict(stamp=message.header.stamp.to_sec(), pose=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]))
    subscriptions = [rospy.Subscriber('/go2w_lio/profile', String, profile, queue_size=1000),
                     rospy.Subscriber('/go2w_lio/processing_lag', Float64, lambda m:emit('lag',dict(seconds=m.data)), queue_size=100),
                     rospy.Subscriber('/go2w_lio/odometry', Odometry, odometry, queue_size=1000)]
    try:
        rospy.spin()
    except KeyboardInterrupt:
        pass
