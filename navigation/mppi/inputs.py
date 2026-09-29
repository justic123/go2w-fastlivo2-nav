"""Nav2 inputs. live mode is read-only; simulation integrates only a virtual robot."""
import os,json,time,math,socket,struct,threading
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2,PointField
from geometry_msgs.msg import TransformStamped,Twist
from rosgraph_msgs.msg import Clock
from tf2_ros import TransformBroadcaster,StaticTransformBroadcaster
ROOT=Path('/state');MODE=os.environ.get('MPPI_MODE','live');SESSION=os.environ.get('MPPI_SESSION','simulation')
def stamp(t):
 from builtin_interfaces.msg import Time
 return Time(sec=int(t),nanosec=int((t-int(t))*1e9))
def yaw(q):return math.atan2(2*(q[3]*q[2]+q[0]*q[1]),1-2*(q[1]*q[1]+q[2]*q[2]))
def angle(x):return math.atan2(math.sin(x),math.cos(x))
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  a=c.recv(n-len(b))
  if not a:raise EOFError()
  b.extend(a)
 return b
class Inputs(Node):
 def __init__(self):
  super().__init__('mppi_inputs');self.tf=TransformBroadcaster(self);self.static=StaticTransformBroadcaster(self)
  self.op=self.create_publisher(Odometry,'/mppi/odom',10);self.cp=self.create_publisher(PointCloud2,'/mppi/cloud',5);self.cl=self.create_publisher(Clock,'/clock',10)
  self.waiting=[];self.previous=None;self.pose=None;self.cloud_stamp=None;self.source_clock=None;self.received={};self.counts={};self.fault=None
  self.pending={};self.lock=threading.Lock();self.cmd=[0.,0.];self.cmd_t=0.;self.virtual=[0.,0.,0.];self.last_sim=time.monotonic()
  self.create_subscription(Twist,'/mppi/cmd_vel_smoothed',self.command,10)
  if MODE=='live':
   import yaml
   e=yaml.safe_load(Path('/desktop/livo.yaml').read_text())['extrin_calib'];R=np.array(e['extrinsic_R']).reshape(3,3);t=e['extrinsic_T']
   # The base reference remains the FAST-LIVO IMU reference used by the old adapter.
   # Existing calibration is a rotation about z (validate instead of guessing).
   if not np.allclose(R[2], [0.,0.,1.]) or not np.allclose(R[:,2],[0.,0.,1.]):
    raise ValueError('Non-planar calibration requires a general quaternion conversion')
   a=math.atan2(R[1,0],R[0,0]);q=[0.,0.,math.sin(a/2),math.cos(a/2)]
  else:t=[0.,0.,0.];q=[0.,0.,0.,1.]
  tr=TransformStamped();tr.header.frame_id='go2w_mppi_base';tr.child_frame_id='go2w_mppi_lidar'
  tr.transform.translation.x,tr.transform.translation.y,tr.transform.translation.z=map(float,t)
  tr.transform.rotation.x,tr.transform.rotation.y,tr.transform.rotation.z,tr.transform.rotation.w=q;self.static.sendTransform(tr)
  if MODE=='live':threading.Thread(target=self.receive,daemon=True).start()
  self.create_timer(.02,self.tick);self.create_timer(.2,self.report)
 def command(self,m):self.cmd=[m.linear.x,m.angular.z];self.cmd_t=time.monotonic()
 def receive(self):
  while rclpy.ok():
   try:
    with socket.create_connection(('127.0.0.1',11339),timeout=2) as c:
     c.settimeout(2)
     while rclpy.ok():
      n,size=struct.unpack('!II',exact(c,8))
      if n>16384 or size>16000000:raise ValueError('Oversize packet')
      d=json.loads(exact(c,n));raw=exact(c,size)
      if d['session']!=SESSION:raise ValueError('Mapping session changed; restart MPPI explicitly')
      with self.lock:self.pending[d['kind']]=(d,raw,time.monotonic())
   except (OSError,EOFError):time.sleep(.3)
   except (ValueError,KeyError) as e:self.fault=str(e);return
 def pose_msg(self,v,t):
  if self.previous and t<=self.previous[1]:return
  m=Odometry();m.header.frame_id='camera_init';m.child_frame_id='go2w_mppi_base';m.header.stamp=stamp(t)
  m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z=map(float,v[:3]);m.pose.pose.orientation.x,m.pose.pose.orientation.y,m.pose.pose.orientation.z,m.pose.pose.orientation.w=map(float,v[3:])
  if self.previous:
   old,ot=self.previous;dt=t-ot;a=yaw(v[3:]);dx=(v[0]-old[0])/dt;dy=(v[1]-old[1])/dt
   m.twist.twist.linear.x=math.cos(a)*dx+math.sin(a)*dy;m.twist.twist.linear.y=-math.sin(a)*dx+math.cos(a)*dy;m.twist.twist.angular.z=angle(a-yaw(old[3:]))/dt
  tr=TransformStamped();tr.header=m.header;tr.child_frame_id=m.child_frame_id;tr.transform.translation.x,tr.transform.translation.y,tr.transform.translation.z=map(float,v[:3]);tr.transform.rotation=m.pose.pose.orientation
  self.tf.sendTransform(tr);self.op.publish(m);self.previous=(v,t);self.pose=dict(pose=v,stamp=t);self.received['odom']=time.monotonic()
 def cloud_msg(self,xyz,t):
  xyz=np.asarray(xyz,dtype='<f4');xyz=xyz[np.isfinite(xyz).all(axis=1)]
  if MODE=='live' and len(xyz):
   # Navigation-only 5 cm voxel filtering; FAST-LIVO2 keeps its original cloud.
   _,idx=np.unique(np.floor(xyz/.05).astype(np.int32),axis=0,return_index=True);xyz=xyz[idx]
  m=PointCloud2();m.header.frame_id='go2w_mppi_lidar';m.header.stamp=stamp(t);m.height=1;m.width=len(xyz);m.point_step=12;m.row_step=len(xyz)*12;m.is_dense=True
  m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(['x','y','z'])];m.data=xyz.tobytes();self.cp.publish(m);self.cloud_stamp=t;self.received['cloud']=time.monotonic()
 def tick(self):
  if MODE=='simulation':
   now=time.monotonic();dt=min(now-self.last_sim,.1);self.last_sim=now;t=time.time()
   vx,w=self.cmd if now-self.cmd_t<.3 else (0.,0.);x,y,a=self.virtual;x+=vx*math.cos(a)*dt;y+=vx*math.sin(a)*dt;a=angle(a+w*dt);self.virtual=[x,y,a]
   self.source_clock=t;self.received['clock']=now;self.cl.publish(Clock(clock=stamp(t)));self.pose_msg([x,y,0.,0.,0.,math.sin(a/2),math.cos(a/2)],t)
   if now-self.received.get('cloud',0)>.09:
    rays=np.linspace(-math.pi,math.pi,720,endpoint=False);pts=[]
    for r in rays:
     dx=math.cos(r+a);dy=math.sin(r+a);dist=min((5-x)/dx if dx>0 else (-5-x)/dx if dx<0 else 1e6,(5-y)/dy if dy>0 else (-5-y)/dy if dy<0 else 1e6)
     pts.append([dist*math.cos(r),dist*math.sin(r),.3])
    self.cloud_msg(pts,t)
   return
  with self.lock:batch=self.pending;self.pending={}
  for k in ('clock','odom','cloud'):
   if k not in batch:continue
   d,raw,rx=batch[k]
   if time.monotonic()-rx>.3:continue
   t=d['stamp']
   if k=='clock':
    if self.source_clock is not None and t<self.source_clock:self.fault='Source clock moved backwards';continue
    self.source_clock=t;self.received['clock']=rx;self.cl.publish(Clock(clock=stamp(t)))
   elif k=='odom':
    if d['frame']!='camera_init' or not np.isfinite(d['pose']).all():self.fault='Invalid odometry';continue
    self.pose_msg(d['pose'],t)
   else:
    fs={f[0]:f for f in d['fields']}
    if any(fs[k][2]!=7 for k in ('x','y','z')):self.fault='Unexpected cloud format';continue
    dtype=np.dtype(dict(names=['x','y','z'],formats=[('>' if d['bigendian'] else '<')+'f4']*3,offsets=[fs[k][1] for k in ('x','y','z')],itemsize=d['point_step']))
    arr=np.ndarray((d['height'],d['width']),dtype=dtype,buffer=raw,strides=(d['row_step'],d['point_step']));xyz=np.column_stack([arr[k].ravel() for k in ('x','y','z')]);self.waiting.append((xyz,t,time.monotonic()));self.waiting=self.waiting[-4:]
  # Publish raw clouds only after the fusion TF covers their original stamps.
  # This avoids feeding MessageFilter future-stamped clouds on every scan.
  for item in self.waiting[:]:
   xyz,t,rx=item
   if time.monotonic()-rx>.4:self.waiting=[v for v in self.waiting if v is not item];continue
   if self.previous and self.previous[1]>=t and time.monotonic()-self.received.get('odom',0)>.025:
    self.cloud_msg(xyz,t);self.waiting=[v for v in self.waiting if v is not item]
 def report(self):
  now=time.monotonic();clock=self.source_clock
  d=dict(mode=MODE,session=SESSION,actuation_enabled=False,fault=self.fault,pose=self.pose,source_clock=clock,
   pose_age_s=None if self.pose is None or clock is None else clock-self.pose['stamp'],cloud_age_s=None if clock is None or self.cloud_stamp is None else clock-self.cloud_stamp,
   receipt_ages={k:now-v for k,v in self.received.items()},updated=time.time())
  d['ready']=not self.fault and all(d['receipt_ages'].get(k,999)<.6 for k in ('clock','odom','cloud')) and all(d[k] is not None and -.05<=d[k]<.6 for k in ('pose_age_s','cloud_age_s'))
  tmp=ROOT/'input.tmp';tmp.write_text(json.dumps(d));tmp.replace(ROOT/'input.json')
rclpy.init();n=Inputs()
try:rclpy.spin(n)
finally:n.destroy_node();rclpy.shutdown()
