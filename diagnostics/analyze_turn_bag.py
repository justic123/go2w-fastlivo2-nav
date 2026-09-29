#!/usr/bin/env python3
"""Read-only turn diagnostics; gyro integration is not ground truth."""
import sys,json,math
from pathlib import Path
import numpy as np,rosbag
root=Path(sys.argv[1]);imu=[];odom=[]
with rosbag.Bag(str(root/'sensors.bag')) as bag:
 for topic,m,t in bag.read_messages(topics=['/go2w_lio/imu','/go2w_lio/odometry']):
  ts=m.header.stamp.to_sec()
  if topic.endswith('/imu'):imu.append([ts,m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z])
  else:
   q=m.pose.pose.orientation;p=m.pose.pose.position
   yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
   odom.append([ts,yaw,p.x,p.y,p.z])
a=np.array(imu);b=np.array(odom);origin=a[0,0];a[:,0]-=origin;b[:,0]-=origin
out=dict(imu_rows=len(a),odom_rows=len(b),windows=[],ground_truth_available=False)
for lo in range(0,180,10):
 x=a[(a[:,0]>=lo)&(a[:,0]<lo+10)];y=b[(b[:,0]>=lo)&(b[:,0]<lo+10)]
 if len(x)<2 or len(y)<2:continue
 out['windows'].append(dict(start_s=lo,gyro_peak_rad_s=np.abs(x[:,1:]).max(0).tolist(),gyro_integral_deg=(np.trapz(x[:,1:],x[:,0],axis=0)*180/np.pi).tolist(),yaw_first_last_deg=(np.unwrap(y[:,1])[[0,-1]]*180/np.pi).tolist()))
(root/'turn_analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
