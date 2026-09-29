"""Save current-session navigation grid; unknown cells remain unknown."""
import json,time
from pathlib import Path
import numpy as np,yaml,rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid

def encode_grid(data,width,height):
 a=np.asarray(data,dtype=np.int16).reshape(height,width)
 if not np.any(a==0) or not np.any(a>=0):raise ValueError('No observed free cells')
 if np.any((a < -1)|(a>100)):raise ValueError('Invalid occupancy values')
 # Inflation is recomputed after reload. Preserve lethal + inscribed as occupied.
 image=np.full(a.shape,205,dtype=np.uint8);image[(a>=0)&(a<99)]=254;image[a>=99]=0
 return image[::-1].tobytes()

def main():
 root=Path('/state');rclpy.init();n=rclpy.create_node('demo_freeze');maps=[]
 n.create_subscription(OccupancyGrid,'/global_costmap/costmap',lambda m:maps.append(m),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
 end=time.monotonic()+10;poses=[];session=None
 try:
  while time.monotonic()<end:
   rclpy.spin_once(n,timeout_sec=.1)
   d=json.loads((root/'input.json').read_text())
   if not d['ready'] or not 0<=time.time()-d['updated']<1:raise RuntimeError('Inputs not fresh')
   session=session or d['session']
   if d['session']!=session:raise RuntimeError('Session changed')
   poses.append(d['pose']['pose'])
   if len(maps)>=2 and len(poses)>=20:break
  if len(maps)<2:raise RuntimeError('Need two fresh map publications')
  a=np.array(poses)
  if np.max(np.linalg.norm(a[:,:3]-a[-1,:3],axis=1))>.025:raise RuntimeError('Keep stationary to finish mapping')
  qs=a[:,3:];dots=np.clip(np.abs(qs@qs[-1]),0,1)
  if np.max(2*np.arccos(dots))>.025:raise RuntimeError('Rotation detected; keep stationary')
  m=maps[-1]
  if m.header.frame_id!='camera_init':raise RuntimeError('Finish only an unselected mapping session')
  q=m.info.origin.orientation
  if abs(q.x)+abs(q.y)+abs(q.z)>1e-6:raise RuntimeError('Rotated grid unsupported')
  data=encode_grid(m.data,m.info.width,m.info.height);out=root/('frozen-map-'+str(time.time_ns()));out.mkdir(exist_ok=False)
  (out/'map.pgm').write_bytes(('P5\n%d %d\n255\n'%(m.info.width,m.info.height)).encode()+data)
  (out/'map.yaml').write_text(yaml.safe_dump(dict(image='map.pgm',resolution=m.info.resolution,origin=[m.info.origin.position.x,m.info.origin.position.y,0.],negate=0,occupied_thresh=.65,free_thresh=.196)))
  (out/'metadata.json').write_text(json.dumps(dict(session=session,saved_at=time.time(),frame='camera_init',note='Observed navigation costmap snapshot; unknown preserved, inflation recomputed'),indent=2));print(str(out))
 finally:n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
