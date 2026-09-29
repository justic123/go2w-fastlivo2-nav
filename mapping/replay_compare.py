#!/usr/bin/env python3
"""Replay only recorded sensor inputs on an isolated ROS master; no robot commands."""
import sys,time,json,math,threading
from pathlib import Path
import rosbag,rospy,cv2,numpy as np
from sensor_msgs.msg import PointCloud2,Imu,Image
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
bagpath,outpath,mode=sys.argv[1:4]
window=float(sys.argv[4]) if len(sys.argv)>4 else 100.
rate=float(sys.argv[5]) if len(sys.argv)>5 else .5
assert 0 < window <= 240 and 0 < rate <= 1
out=Path(outpath);cv2.setNumThreads(1)
rospy.init_node('recorded_sensor_comparison')
pubs={'/go2w_lio/points':rospy.Publisher('/go2w_lio/points',PointCloud2,queue_size=10),'/go2w_lio/imu':rospy.Publisher('/go2w_lio/imu',Imu,queue_size=2000)}
if mode=='livo':pubs['/go2w_livo/jpeg']=rospy.Publisher('/go2w_livo/image_raw',Image,queue_size=10)
clk=rospy.Publisher('/clock',Clock,queue_size=10)
rows=[];bad=threading.Event();reason=[];f=(out/'odometry.jsonl').open('w');startstamp=[None]
def cb(m):
 v=[m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z];q=m.pose.pose.orientation
 r=math.sqrt(sum(x*x for x in v));row={'stamp':m.header.stamp.to_sec(),'position':v,'radius':r,'quaternion_xyzw':[q.x,q.y,q.z,q.w]}
 rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
 if not all(math.isfinite(x) for x in v+[q.x,q.y,q.z,q.w]):reason.append('nonfinite odometry');bad.set()
 elif r>20:reason.append('20m diagnostic radius exceeded');bad.set()
sub=rospy.Subscriber('/go2w_lio/odometry',Odometry,cb,queue_size=2000)
cloud_stats={'messages':0,'nonempty':0,'points':0,'max_points':0}
def cloud_cb(m):
 n=m.width*m.height;cloud_stats['messages']+=1;cloud_stats['nonempty']+=int(n>0);cloud_stats['points']+=n;cloud_stats['max_points']=max(cloud_stats['max_points'],n)
cloud_sub=rospy.Subscriber('/go2w_lio/cloud',PointCloud2,cloud_cb,queue_size=10)
counts={k:0 for k in pubs};failure=None;elapsed=0.;lastimg=-1e30
try:
 deadline=time.monotonic()+20
 while not all(p.get_num_connections() for p in pubs.values()):
  if time.monotonic()>deadline:raise RuntimeError('Input subscriber readiness timeout')
  time.sleep(.1)
 with rosbag.Bag(bagpath) as bag:
  start=bag.get_start_time();startstamp[0]=start;wall=time.monotonic()
  for topic,m,t in bag.read_messages(topics=list(pubs)):
   elapsed=t.to_sec()-start
   if elapsed>window or bad.is_set():break
   delay=wall+elapsed/rate-time.monotonic()
   if delay>0:time.sleep(delay)
   clock=Clock();clock.clock=t;clk.publish(clock)
   if topic=='/go2w_livo/jpeg':
    stamp=m.header.stamp.to_sec()
    if stamp-lastimg<.4:continue
    lastimg=stamp
    a=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_COLOR)
    if a is None or a.shape!=(1080,1920,3):raise RuntimeError('Unexpected image size')
    a=cv2.resize(a,(640,360),interpolation=cv2.INTER_AREA)
    im=Image();im.header=m.header;im.height=360;im.width=640;im.encoding='bgr8';im.step=1920;im.data=a.tobytes();m=im
   pubs[topic].publish(m);counts[topic]+=1
 time.sleep(3)
except Exception as e:failure=str(e)
finally:
 sub.unregister();f.close()
 cloud_sub.unregister()
 result={'cloud_output':cloud_stats,'mode':mode,'rate':rate,'requested_bag_seconds':window,'bag_start':startstamp[0],'replayed_bag_seconds':elapsed,'published':counts,'odometry_count':len(rows),'max_radius_m':max([r['radius'] for r in rows],default=None),'last_odometry':rows[-1] if rows else None,'stop_reason':failure or (reason[0] if reason else 'window complete'),'image_selection':'JPEG source stamp >=0.4s apart; original live frame selection unavailable'}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if failure:sys.exit(1)
