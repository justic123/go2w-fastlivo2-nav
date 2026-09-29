#!/usr/bin/env python3
import rosbag,numpy as np,json,sys
rows={'imu':[],'points':[]};a=[];g=[];spans=[]
with rosbag.Bag(sys.argv[1]) as b:
 start=b.get_start_time()
 for topic,m,t in b.read_messages(topics=['/go2w_lio/imu','/go2w_lio/points']):
  if t.to_sec()-start>100:break
  key=topic.rsplit('/',1)[1];rows[key].append([m.header.stamp.to_sec(),t.to_sec()])
  if key=='imu':
   a.append([m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z]);g.append([m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z])
  else:
   f=next(f for f in m.fields if f.name=='timestamp');dt=np.dtype({'names':['t'],'formats':['<f8'],'offsets':[f.offset],'itemsize':m.point_step});ts=np.frombuffer(m.data,dtype=dt)['t'];spans.append([float(ts.min()),float(ts.max())])
def stat(x):
 x=np.asarray(x);return {'min':float(x.min()),'median':float(np.median(x)),'p95':float(np.quantile(x,.95)),'max':float(x.max())}
out={}
for k,rr in rows.items():
 rr=np.asarray(rr);d=np.diff(rr[:,0]);out[k]={'count':len(rr),'stamp_delta_seconds':stat(d),'nonpositive_deltas':int((d<=0).sum()),'record_minus_header_seconds':stat(rr[:,1]-rr[:,0])}
s=np.asarray(spans);out['scan_span_seconds']=stat(s[:,1]-s[:,0]);out['next_scan_start_minus_previous_end_seconds']=stat(s[1:,0]-s[:-1,1]);out['scan_overlap_count']=int((s[1:,0]<s[:-1,1]-.001).sum())
a=np.asarray(a);g=np.asarray(g);times=np.asarray(rows['imu'])[:,1]-start
for name,mask in [('stationary_0_50s',times<50),('motion_60_100s',times>=60)]:
 out[name]={'acc_mean_xyz':a[mask].mean(axis=0).tolist(),'acc_norm':stat(np.linalg.norm(a[mask],axis=1)),'gyro_norm':stat(np.linalg.norm(g[mask],axis=1))}
print(json.dumps(out,indent=2))
