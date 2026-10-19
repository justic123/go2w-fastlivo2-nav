"""Saved-map validation. ICP runs outside the ROS/TF heartbeat process."""
import array,json,time,multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from status_store import publish as publish_status
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import QoSProfile,DurabilityPolicy
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import PointCloud2,PointField
from nav_msgs.msg import Odometry
from tf2_ros import Buffer,TransformListener,TransformBroadcaster
from scipy.spatial.transform import Rotation
from localization_policy import fresh_scan,correction_allowed,ValidationWindow,registration_problem,completed_trial_problem
import registration_worker


def main():
 root=Path('/state');sel=json.loads(Path('/work/selection.json').read_text());session=sel['source_session'];T=np.array(sel['transform'],dtype=float)
 maproot=Path('/work/maps')/sel['map_id']
 rclpy.init();n=Node('saved_map_localization',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)])
 buf=Buffer();listener=TransformListener(buf,n);broadcaster=TransformBroadcaster(n)
 latest=None;pose=None;fault=None;last_trial=0.;stats={};validations=0
 latest_received=0.;pose_received=0.;validated_stamp=None;issue=None;pending=None
 window=ValidationWindow()
 # One worker and at most one outstanding job: ICP cannot queue old observations
 # or hold the Python GIL of ROS subscriptions, TF, and the readiness heartbeat.
 pool=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),
                          initializer=registration_worker.initialize,initargs=(str(maproot/'points.npy'),))
 qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL);mp=n.create_publisher(PointCloud2,'/saved_map/cloud',qos)
 a=np.load(maproot/'points.npy').astype('<f4');m=PointCloud2();m.header.frame_id='map';m.height=1;m.width=len(a);m.point_step=12;m.row_step=len(a)*12
 m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(('x','y','z'))];m.data=array.array('B',a.tobytes());m.is_dense=True;mp.publish(m)
 def cloud(msg):
  nonlocal latest,latest_received
  latest=msg;latest_received=time.monotonic()
 def odom(msg):
  nonlocal pose,pose_received
  pose=msg;pose_received=time.monotonic()
 n.create_subscription(PointCloud2,'/mppi/cloud',cloud,1);n.create_subscription(Odometry,'/mppi/odom',odom,1)
 def stationary():
  return pose is not None and correction_allowed(pose.twist.twist.linear.x,pose.twist.twist.linear.y,pose.twist.twist.angular.z,time.monotonic()-pose_received,(root/'motion_active').exists())
 def report():
  good=not fault and window.ready(time.monotonic())
  data=dict(ready=good,fault=fault,issue=issue,consecutive_validations=window.consecutive,map_id=sel['map_id'],source_session=session,transform=T.tolist(),stats=stats,validations=validations,updated=time.time(),icp_pending=pending is not None,icp_pending_age_s=None if pending is None else time.monotonic()-pending['started'])
  publish_status(root,'localization',data)
 def reject(message,stamp):
  nonlocal issue
  issue=message;window.observe(False,stamp,time.monotonic())
 def finish(job,d):
  nonlocal T,stats,issue,validated_stamp,validations
  now=time.monotonic();stamp=job['stamp']
  result=job['future'].result()
  problem=completed_trial_problem(now-job['started'],d.get('ready',False),time.time()-d.get('updated',0))
  candidate=result['candidate'];base=job['transform'];delta=np.linalg.inv(base)@candidate
  shift=float(np.linalg.norm(delta[:3,3]));turn=float(np.linalg.norm(Rotation.from_matrix(delta[:3,:3]).as_rotvec()))
  stats=dict(fitness=result['fitness'],rmse=result['rmse'],correction_m=shift,correction_rad=turn,points=len(result['points']),scan_stamp=stamp,processing_s=result['processing_s'],total_job_s=now-job['started'])
  if pose is not None:
   p=pose.pose.pose.position;point=np.array([p.x,p.y,p.z,1.]);stats['correction_at_robot_m']=float(np.linalg.norm((candidate@point-base@point)[:3]));stats['robot_pose']=[p.x,p.y,p.z]
  problem=problem or registration_problem(result['fitness'],result['rmse'],shift,turn)
  with (root/'localization-history.jsonl').open('a') as history:
   history.write(json.dumps(dict(updated=time.time(),accepted=problem is None,reason=problem,stats=stats))+'\n')
  if problem:
   if issue!=problem:
    with (root/'localization-rejection.tmp').open('wb') as f:np.savez_compressed(f,points=result['points'],current=base,candidate=candidate)
    (root/'localization-rejection.tmp').replace(root/'localization-rejection.npz')
    (root/'localization-rejection.json').write_text(json.dumps(dict(updated=time.time(),map_id=sel['map_id'],stats=stats)))
   reject(problem,stamp);return
  issue=None;window.observe(True,stamp,job['started']);validated_stamp=stamp;validations+=1
  if job['stationary'] and stationary():
   factor=min(1.,.01/max(shift,1e-9),.01/max(turn,1e-9));T[:3,3]+=factor*(candidate[:3,3]-T[:3,3]);T[:3,:3]=T[:3,:3]@Rotation.from_rotvec(Rotation.from_matrix(delta[:3,:3]).as_rotvec()*factor).as_matrix()
 def tick():
  nonlocal fault,last_trial,stats,pending
  if fault:report();return
  try:d=json.loads((root/'input.json').read_text())
  except (OSError,ValueError):reject('Input status unavailable',None);report();return
  if d['session']!=session:fault='Saved transform belongs to a different mapping session';report();return
  now=time.monotonic()
  tr=TransformStamped();tr.header.frame_id='map';tr.child_frame_id='camera_init';tr.header.stamp=n.get_clock().now().to_msg()
  tr.transform.translation.x,tr.transform.translation.y,tr.transform.translation.z=map(float,T[:3,3]);q=Rotation.from_matrix(T[:3,:3]).as_quat();tr.transform.rotation.x,tr.transform.rotation.y,tr.transform.rotation.z,tr.transform.rotation.w=map(float,q);broadcaster.sendTransform(tr)
  if pending is not None:
   if pending['future'].done():
    job=pending;pending=None
    try:finish(job,d)
    except Exception as e:reject(str(e),job['stamp'])
   elif now-pending['started']>=2:reject('Map validation worker exceeded 2s; waiting without motion',pending['stamp'])
  if pending is None and latest is not None and now-last_trial>2:
   last_trial=now;stamp=latest.header.stamp.sec+latest.header.stamp.nanosec*1e-9
   if not d.get('ready') or not 0<=time.time()-d.get('updated',0)<1 or not fresh_scan(stamp,n.get_clock().now().nanoseconds*1e-9,now-latest_received,validated_stamp):
    reject('Need a new fresh scan and healthy inputs',stamp);report();return
   try:
    tf=buf.lookup_transform('camera_init',latest.header.frame_id,Time.from_msg(latest.header.stamp));p=tf.transform.translation;q=tf.transform.rotation
    R=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix();a=np.frombuffer(latest.data,dtype='<f4').reshape(-1,3);a=a@R.T+np.array([p.x,p.y,p.z])
    base=T.copy();pending=dict(future=pool.submit(registration_worker.match,a,base),stamp=stamp,started=now,transform=base,stationary=stationary())
   except Exception as e:reject(str(e),stamp);stats=dict(waiting=str(e))
  report()
 n.create_timer(.05,tick)
 try:rclpy.spin(n)
 except KeyboardInterrupt:pass
 finally:
  pool.shutdown(wait=False,cancel_futures=True);n.destroy_node();rclpy.try_shutdown()

if __name__=='__main__':main()
