import rosbag,rospy,json,statistics
from collections import defaultdict
p='/work/runs/desktop-20260928-161404/sensors.bag'
b=rosbag.Bag(p);end=b.get_end_time();out={}
for off in [10,5,2]:
 d=defaultdict(list)
 for topic,m,t in b.read_messages(topics=['/go2w_lio/imu','/go2w_lio/points','/go2w_livo/jpeg','/go2w_lio/odometry'],start_time=rospy.Time.from_sec(end-off),end_time=rospy.Time.from_sec(end-off+2)):
  d[topic].append(t.to_sec()-m.header.stamp.to_sec())
 out[off]={k:dict(n=len(v),min=min(v),median=statistics.median(v),max=max(v)) for k,v in d.items()}
print(json.dumps(out,indent=2))
