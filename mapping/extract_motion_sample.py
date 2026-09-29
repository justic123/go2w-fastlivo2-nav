import rosbag,numpy as np,sys
clouds=[];times=[];imus=[]
with rosbag.Bag(sys.argv[1]) as b:
 origin=b.get_start_time()
 for topic,m,t in b.read_messages(topics=['/go2w_lio/points','/go2w_lio/imu']):
  ts=m.header.stamp.to_sec()-origin
  if t.to_sec()-origin>78:break
  if not 58<=ts<=77:continue
  if topic.endswith('imu'):
   imus.append([ts,m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z,m.linear_acceleration.x,m.linear_acceleration.y,m.linear_acceleration.z]);continue
  dt=np.dtype({'names':['x','y','z'],'formats':['<f4']*3,'offsets':[0,4,8],'itemsize':m.point_step});a=np.frombuffer(m.data,dtype=dt);p=np.column_stack([a[x] for x in ['x','y','z']]);p=p[np.isfinite(p).all(axis=1)];d=np.linalg.norm(p,axis=1);p=p[(d>1)&(d<20)];_,ids=np.unique(np.floor(p/.15).astype(int),axis=0,return_index=True);clouds.append(p[ids]);times.append(ts)
np.savez_compressed(sys.argv[2],times=times,imu=imus,**{'p'+str(i):p for i,p in enumerate(clouds)})
print(len(clouds),len(imus))
