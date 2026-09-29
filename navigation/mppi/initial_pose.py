"""Show the saved cloud and capture a user hint. No map->odom TF or actuation."""
import argparse,json,time,math,yaml
from pathlib import Path
import numpy as np,rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from sensor_msgs.msg import PointCloud2,PointField
from geometry_msgs.msg import PoseWithCovarianceStamped,PoseStamped
from nav_msgs.msg import OccupancyGrid
from visualization_msgs.msg import Marker,MarkerArray
from nav_msgs.msg import Path as RosPath
from mission_view import messages as mission_messages
p=argparse.ArgumentParser();p.add_argument('--map-id',required=True);p.add_argument('--map-root',default='/work/maps');p.add_argument('--state-dir',default='/state');p.add_argument('--display-only',action='store_true');args=p.parse_args()
if Path(args.map_id).name!=args.map_id or args.map_id in ('.','..'):raise ValueError('Invalid map id')
root=Path(args.state_dir);maproot=Path(args.map_root)/args.map_id;rclpy.init();n=Node('saved_map_display' if args.display_only else 'saved_map_initial_pose');q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
pub=n.create_publisher(PointCloud2,'/demo/saved_cloud',q)
a=np.load(maproot/'points.npy').astype('<f4');m=PointCloud2();m.header.frame_id='map';m.height=1;m.width=len(a);m.point_step=12;m.row_step=len(a)*12;m.is_dense=True;m.fields=[PointField(name=k,offset=i*4,datatype=7,count=1) for i,k in enumerate(('x','y','z'))];m.data=a.tobytes();pub.publish(m)
# Our saved maps use a binary 8-bit PGM; reject unsupported formats explicitly.
cfg=yaml.safe_load((maproot/'map.yaml').read_text())
with (maproot/cfg['image']).open('rb') as f:
 if f.readline().strip()!=b'P5':raise ValueError('Expected binary PGM')
 line=f.readline()
 while line.startswith(b'#'):line=f.readline()
 width,height=map(int,line.split())
 if f.readline().strip()!=b'255':raise ValueError('Expected 8-bit PGM')
 pixels=np.frombuffer(f.read(),dtype=np.uint8).reshape(height,width)[::-1]
occ=pixels/255. if cfg.get('negate') else (255.-pixels)/255.;grid=np.full(pixels.shape,-1,dtype=np.int8);grid[occ<cfg['free_thresh']]=0;grid[occ>cfg['occupied_thresh']]=100
g=OccupancyGrid();g.header.frame_id='map';g.info.width=width;g.info.height=height;g.info.resolution=float(cfg['resolution']);g.info.origin.position.x=float(cfg['origin'][0]);g.info.origin.position.y=float(cfg['origin'][1]);g.info.origin.position.z=-.02;g.info.origin.orientation.z=math.sin(cfg['origin'][2]/2);g.info.origin.orientation.w=math.cos(cfg['origin'][2]/2);g.data=grid.ravel().tolist()
gp=n.create_publisher(OccupancyGrid,'/demo/saved_map',q);gp.publish(g)
status_pub=n.create_publisher(Marker,'/demo/view_status',q)
mission_pub=n.create_publisher(MarkerArray,'/demo/mission',q);plan_pub=n.create_publisher(RosPath,'/demo/route_plan',q)
def show_status():
 ready=False
 try:
  current=json.loads((Path(args.map_root).parent/'current.json').read_text());folder=Path(current['folder'])
  runtime=json.loads((folder/'runtime.json').read_text());loc=json.loads((folder/'localization.json').read_text())
  ready=runtime['phase']=='running' and loc.get('ready') and loc['map_id']==args.map_id and loc['source_session']==current['session'] and 0<=time.time()-loc['updated']<2 and 0<=time.time()-runtime['updated']<2
 except (OSError,ValueError,KeyError):pass
 msg=Marker();msg.header.frame_id='map';msg.ns='service_status';msg.id=0;msg.type=Marker.TEXT_VIEW_FACING;msg.action=Marker.ADD;msg.pose.orientation.w=1.;msg.pose.position.y=3.;msg.pose.position.z=.5;msg.scale.z=.22;msg.color.a=1.;msg.color.r=0.2 if ready else 1.;msg.color.g=1. if ready else .3;msg.color.b=.2
 msg.text=('LOCALIZATION LIVE - check path before motion' if ready else 'SAVED MAP ONLY - localization unavailable')+'\n'+args.map_id
 status_pub.publish(msg)
 markers,plan=mission_messages(maproot);mission_pub.publish(markers);plan_pub.publish(plan)
show_status();n.create_timer(.5,show_status)
def cb(msg):
 if msg.header.frame_id!='map':return
 inp=json.loads((root/'input.json').read_text())
 if not inp.get('ready') or not 0<=time.time()-inp['updated']<1:return
 pos=msg.pose.pose.position;rot=msg.pose.pose.orientation
 values=[pos.x,pos.y,pos.z,rot.x,rot.y,rot.z,rot.w]
 if not np.isfinite(values).all() or abs(sum(x*x for x in values[3:])-1)>.02:return
 data=dict(map_id=args.map_id,source_session=inp['session'],created=time.time(),map_pose=values,odom_pose=inp['pose']['pose'])
 temp=root/'initial_pose.tmp';temp.write_text(json.dumps(data));temp.replace(root/'initial_pose.json');print('Initial pose recorded; no transform activated',flush=True)
if not args.display_only:n.create_subscription(PoseWithCovarianceStamped,'/initialpose',cb,10)
def target_click(msg):
 if msg.header.frame_id!='map':return
 pos=msg.pose.position;rot=msg.pose.orientation;v=[pos.x,pos.y,rot.x,rot.y,rot.z,rot.w]
 if not np.isfinite(v).all() or abs(sum(x*x for x in v[2:])-1)>.02:return
 yaw=math.atan2(2*(rot.w*rot.z+rot.x*rot.y),1-2*(rot.y*rot.y+rot.z*rot.z));d=dict(map_id=args.map_id,pose=[pos.x,pos.y,yaw],created=time.time())
 tmp=maproot/'clicked_goal.tmp';tmp.write_text(json.dumps(d));tmp.replace(maproot/'clicked_goal.json')
# Deliberately isolated from Nav2's /goal_pose: a click is data, never a navigation command.
if args.display_only:n.create_subscription(PoseStamped,'/demo/goal_pose',target_click,10)
try:rclpy.spin(n)
except KeyboardInterrupt:pass
finally:n.destroy_node();rclpy.try_shutdown()
