import rospy,json,time,sys,statistics
from pathlib import Path
from collections import deque
from std_msgs.msg import Float64
from nav_msgs.msg import Odometry
rospy.init_node('desktop_livo_health');lags=deque(maxlen=100);last=None;pose=None;count=0
out=Path(sys.argv[1])
def lag(m):
 global last
 last=time.time();lags.append(m.data)
def odom(m):
 global pose,count
 p=m.pose.pose.position;pose=[p.x,p.y,p.z];count+=1
rospy.Subscriber('/go2w_lio/processing_lag',Float64,lag,queue_size=10);rospy.Subscriber('/go2w_lio/odometry',Odometry,odom,queue_size=5)
while not rospy.is_shutdown():
 now=time.time();d=dict(updated=now,pose=pose,odom_count=count,lag_samples=len(lags),lag_last_s=lags[-1] if lags else None,lag_median_s=statistics.median(lags) if lags else None,lag_max_s=max(lags) if lags else None,monitor_age_s=now-last if last else None)
 d['ready']=bool(last and now-last<1 and lags and 0<=lags[-1]<.8)
 tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(d));tmp.replace(out);time.sleep(.5)
