import rosbag,json,sys,numpy as np
rows={'imu':[],'points':[]};acc=[];gyro=[]
with rosbag.Bag(sys.argv[1]) as b:
 start=b.get_start_time()
 for topic,m,t in b.read_messages(topics=['/go2w_lio/imu','/go2w_lio/points']):
  if t.to_sec()-start>100:break
  key=topic.rsplit('/',1)[1];rows[key].append([m.header.stamp.to_sec()-start,t.to_sec()-start])
  if key=='imu':
   acc.append([m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z]);gyro.append([m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z])
result={}
for k,a in rows.items():
 a=np.asarray(a);d=np.diff(a[:,0]);ids=np.argsort(d)[-15:][::-1];result[k+'_largest_gaps']=[{'from_s':a[i,0],'to_s':a[i+1,0],'gap_ms':d[i]*1000} for i in ids]
a=np.asarray(acc);g=np.asarray(gyro);t=np.asarray(rows['imu'])[:,0];result['imu_windows']=[]
for start in range(50,81,2):
 mask=(t>=start)&(t<start+2)
 if mask.any():result['imu_windows'].append({'start_s':start,'count':int(mask.sum()),'acc_norm_max':float(np.linalg.norm(a[mask],axis=1).max()),'gyro_norm_max':float(np.linalg.norm(g[mask],axis=1).max()),'gyro_integral_xyz':np.trapz(g[mask],t[mask],axis=0).tolist()})
print(json.dumps(result,indent=2))
