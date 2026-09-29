"""Scan-to-saved-map validation and slow stationary correction; never controls the robot."""
import json,time,math,threading
from pathlib import Path
import numpy as np,open3d as o3d
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import PointCloud2,PointField
from nav_msgs.msg import Odometry
from tf2_ros import Buffer,TransformListener,TransformBroadcaster
from scipy.spatial.transform import Rotation
root=Path('/state');sel=json.loads(Path('/work/selection.json').read_text());session=sel['source_session'];T=np.array(sel['transform'],dtype=float);reg=o3d.pipelines.registration
maproot=Path('/work/maps')/sel['map_id'];target=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.load(maproot/'points.npy')));target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.3,max_nn=40))
rclpy.init();n=Node('saved_map_localization',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)]);buf=Buffer();listener=TransformListener(buf,n);broadcaster=TransformBroadcaster(n);latest=None;pose=None;checked=0.;fault=None;last_trial=0.;stats={};validations=0
qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL);mp=n.create_publisher(PointCloud2,'/saved_map/cloud',qos)
a=np.asarray(target.points).astype('<f4');m=PointCloud2();m.header.frame_id='map';m.height=1;m.width=len(a);m.point_step=12;m.row_step=len(a)*12;m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(('x','y','z'))];m.data=a.tobytes();m.is_dense=True;mp.publish(m)
def cloud(m):
 global latest
 latest=m
def odom(m):
 global pose
 pose=m
n.create_subscription(PointCloud2,'/mppi/cloud',cloud,5);n.create_subscription(Odometry,'/mppi/odom',odom,10)
def tick():
 global T,checked,fault,last_trial,stats,validations
 if fault:
  report();return
 d=json.loads((root/'input.json').read_text())
 if d['session']!=session:fault='Saved transform belongs to a different mapping session';report();return
 now=time.monotonic()
 tr=TransformStamped();tr.header.frame_id='map';tr.child_frame_id='camera_init';tr.header.stamp=n.get_clock().now().to_msg();tr.transform.translation.x,tr.transform.translation.y,tr.transform.translation.z=map(float,T[:3,3]);q=Rotation.from_matrix(T[:3,:3]).as_quat();tr.transform.rotation.x,tr.transform.rotation.y,tr.transform.rotation.z,tr.transform.rotation.w=map(float,q);broadcaster.sendTransform(tr)
 if latest is not None and now-last_trial>2:
  last_trial=now
  try:
   tf=buf.lookup_transform('camera_init',latest.header.frame_id,Time.from_msg(latest.header.stamp));p=tf.transform.translation;q=tf.transform.rotation;R=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix();a=np.frombuffer(latest.data,dtype='<f4').reshape(-1,3);a=a@R.T+np.array([p.x,p.y,p.z]);src=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(a)).voxel_down_sample(.1)
   result=reg.registration_icp(src,target,.2,T,reg.TransformationEstimationPointToPlane(),reg.ICPConvergenceCriteria(max_iteration=25));candidate=result.transformation;delta=np.linalg.inv(T)@candidate;shift=float(np.linalg.norm(delta[:3,3]));turn=float(np.linalg.norm(Rotation.from_matrix(delta[:3,:3]).as_rotvec()))
   stats=dict(fitness=result.fitness,rmse=result.inlier_rmse,correction_m=shift,correction_rad=turn,points=len(src.points))
   if result.fitness<.6 or result.inlier_rmse>.12 or shift>.15 or turn>.12:
    fault='Scan no longer agrees with saved map';report();return
   checked=now;validations+=1
   # Avoid discontinuities during path execution. Validate only while an action owns motion.
   if pose is not None and abs(pose.twist.twist.linear.x)<.015 and abs(pose.twist.twist.angular.z)<.025 and not (root/'motion_active').exists():
    factor=min(1.,.01/max(shift,1e-9),.01/max(turn,1e-9));T[:3,3]+=factor*(candidate[:3,3]-T[:3,3]);T[:3,:3]=T[:3,:3]@Rotation.from_rotvec(Rotation.from_matrix(delta[:3,:3]).as_rotvec()*factor).as_matrix()
  except Exception as e:stats=dict(waiting=str(e))
 report()
def report():
 good=not fault and checked>0 and time.monotonic()-checked<5 and validations>=2
 data=dict(ready=good,fault=fault,map_id=sel['map_id'],source_session=session,transform=T.tolist(),stats=stats,validations=validations,updated=time.time());tmp=root/'localization.tmp';tmp.write_text(json.dumps(data));tmp.replace(root/'localization.json')
n.create_timer(.05,tick)
try:rclpy.spin(n)
except KeyboardInterrupt:pass
finally:n.destroy_node();rclpy.try_shutdown()
