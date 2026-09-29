#!/usr/bin/env python3
"""Visual rotation versus integrated gyro: timing diagnostic, not calibration."""
import sys,json,cv2,numpy as np,rosbag
cv2.setNumThreads(1)
K=np.array([[436.9260867,0,339.5704767],[0,440.08353,212.4589067],[0,0,1.]])
D=np.array([-.415971,.158898,-.015395,-.008031,0.]);ki=np.linalg.inv(K)
imu=[];pairs=[];prev=None
with rosbag.Bag(sys.argv[1]) as bag:
 origin=bag.get_start_time()
 for topic,m,_ in bag.read_messages(topics=['/go2w_lio/imu','/go2w_livo/jpeg']):
  t=m.header.stamp.to_sec()-origin
  if topic.endswith('/imu'):imu.append((t,m.angular_velocity.z));continue
  a=cv2.imdecode(np.frombuffer(m.data,np.uint8),cv2.IMREAD_GRAYSCALE)
  if a is None:continue
  a=cv2.resize(a,(640,360));a=cv2.undistort(a,K,D)
  if prev:
   tp,p=prev;pts=cv2.goodFeaturesToTrack(p,300,.015,10)
   if pts is not None and len(pts)>20:
    nxt,status,err=cv2.calcOpticalFlowPyrLK(p,a,pts,None,winSize=(21,21),maxLevel=3)
    good=status.ravel().astype(bool);p0=pts[good].reshape(-1,2);p1=nxt[good].reshape(-1,2)
    if len(p0)>20:
     H,mask=cv2.findHomography(p0,p1,cv2.RANSAC,2.)
     if H is not None and int(mask.sum())>=20:
      R=ki@H@K;U,S,V=np.linalg.svd(R);R=U@V
      if np.linalg.det(R)>0:
       rot=cv2.Rodrigues(R)[0].ravel();pairs.append([tp,t,float(rot[1]),int(mask.sum()),len(p0)])
  prev=(t,a)
a=np.array(imu);p=np.array(pairs);order=np.argsort(a[:,0]);a=a[order];a=a[np.r_[True,np.diff(a[:,0])>0]]
integ=np.r_[0,np.cumsum(np.diff(a[:,0])*(a[:-1,1]+a[1:,1])*.5)]
res={'note':'Homography rotation uses candidate intrinsics; translation can bias. Not an exposure timestamp calibration.','pairs':pairs,'windows':{}}
for label,lo,hi in [('all',0,185),('first_turn',40,78),('return_turn',78,125)]:
 use=(p[:,0]>lo)&(p[:,1]<hi)&(abs(p[:,2])>.003)&(p[:,3]/p[:,4]>.6);b=p[use]
 scores=[]
 for lag in np.arange(-.4,.201,.01):
  expected=np.interp(b[:,1]+lag,a[:,0],integ)-np.interp(b[:,0]+lag,a[:,0],integ)
  for sign in [1,-1]:scores.append((float(np.median(abs(b[:,2]-sign*expected))) if len(b) else 1e9,float(lag),sign))
 best=min(scores);res['windows'][label]=dict(count=len(b),best_median_error_rad=best[0],best_offset_s=best[1],sign=best[2],scores=scores)
open(sys.argv[2],'w').write(json.dumps(res));print(json.dumps({k:v for k,v in res.items() if k!='pairs'}))
