"""Read-only ROS2 to bounded browser assets. Runs on the robot in Humble."""
import math,struct,time,threading
from pathlib import Path as FilePath
import numpy as np,yaml
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid,Path
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PolygonStamped
from tf2_ros import Buffer,TransformListener
from scipy.spatial.transform import Rotation
from common import ROOT,CACHE,read,atomic,png
CACHE.mkdir(parents=True,exist_ok=True)
view={};pending={};saved_identity=None

def origin(p):
    q=p.orientation
    return [p.position.x,p.position.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))]

def grid(m,key):pending[key]=m

def grid_file(a,key,meta):
    # The PNG has map y increasing upwards. Preserve unknown pixels distinctly.
    gray=np.full(a.shape,92,dtype=np.uint8);known=a>=0;gray[known]=np.clip(244-a[known]*1.85,20,244).astype(np.uint8);gray[a>=99]=20
    atomic(CACHE/(key+'.png'),png(a.shape[1],a.shape[0],gray[::-1].tobytes()))
    ys,xs=np.where(a>=0)
    bounds=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else [0,0,a.shape[1],a.shape[0]]
    view[key]=dict(meta,bounds=bounds,updated=time.time())

def saved():
    global saved_identity
    d=read(ROOT/'demo/state.json');ident=d.get('map_id')
    if ident==saved_identity:return
    view.pop('saved',None);view.pop('saved_cloud',None);view.pop('saved_rgb',None)
    if not ident:saved_identity=None;return
    if '/' in ident or ident in ('.','..'):return
    folder=ROOT/'navigation/mppi/maps'/ident
    cfg=yaml.safe_load((folder/'map.yaml').read_text())
    with (folder/cfg['image']).open('rb') as f:
        if f.readline().strip()!=b'P5':raise ValueError('Only P5 maps supported')
        line=f.readline()
        while line.startswith(b'#'):line=f.readline()
        w,h=map(int,line.split())
        if f.readline().strip()!=b'255' or w*h>16000000:raise ValueError('Unsupported map')
        pixels=np.frombuffer(f.read(),dtype=np.uint8).reshape(h,w)[::-1]
    occ=pixels/255. if cfg.get('negate') else (255.-pixels)/255.;a=np.full((h,w),-1,dtype=np.float32);a[occ<cfg['free_thresh']]=0;a[occ>cfg['occupied_thresh']]=100
    grid_file(a,'saved',dict(width=w,height=h,resolution=cfg['resolution'],origin=cfg['origin'],frame='map',map_id=ident))
    a=np.load(folder/'points.npy',mmap_mode='r');source_count=len(a);a=np.asarray(a[::max(1,math.ceil(len(a)/400000)),:3],dtype='<f4');a=a[np.isfinite(a).all(1)]
    atomic(CACHE/'saved-cloud.bin',a.tobytes());view['saved_cloud']=dict(count=len(a),source_count=source_count,color='height',frame='map',map_id=ident,updated=time.time());saved_identity=ident
    rgb=read(folder/'display-rgb.json')
    if rgb.get('map_id')==ident and rgb.get('frame')=='map' and (folder/'display-rgb.bin').is_file():
        data=(folder/'display-rgb.bin').read_bytes()
        if len(data)==rgb.get('count',0)*24 and 0<rgb['count']<=400000:
            atomic(CACHE/'saved-rgb.bin',data);view['saved_rgb']=dict(rgb,updated=time.time())

rclpy.init();n=Node('go2w_web_readonly',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)])
buf=Buffer();listener=TransformListener(buf,n)
for topic,key in [('/global_costmap/costmap','grid'),('/local_costmap/costmap','local')]:
    n.create_subscription(OccupancyGrid,topic,lambda m,k=key:grid(m,k),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
n.create_subscription(PointCloud2,'/mppi/cloud',lambda m:pending.update(cloud=m),1)
for topic,key in [('/plan','plan'),('/demo/route_plan','route_plan')]:
    n.create_subscription(Path,topic,lambda m,k=key:pending.update({k:m}),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL if key=='route_plan' else DurabilityPolicy.VOLATILE))
n.create_subscription(PolygonStamped,'/local_costmap/published_footprint',lambda m:pending.update(footprint=m),1)
last_map=0.;last_cloud=0.;old_session=None;rgb_tag=None

def tick():
    global last_map,last_cloud,old_session,rgb_tag
    now=time.monotonic();cur=read(ROOT/'navigation/mppi/current.json');session=cur.get('session');selected=read(ROOT/'navigation/mppi/selection.json');target='map' if selected.get('source_session')==session else 'camera_init'
    if session!=old_session:
        for k in ('grid','local','cloud','plan','route_plan','footprint','robot'):view.pop(k,None)
        pending.clear();old_session=session
    view.update(session=session,updated=time.time())
    native=read(CACHE/'native-rgb.json')
    if native.get('session')==session and 0<=time.time()-native.get('updated',0)<3 and native.get('updated')!=rgb_tag:
        try:
            a=np.fromfile(CACHE/'native-rgb.bin',dtype='<f4').reshape(-1,6)
            if len(a)!=native['count'] or read(CACHE/'native-rgb.json')!=native:raise ValueError('RGB snapshot changed')
            if target=='map':
                loc=read(ROOT/'navigation/mppi/runs'/FilePath(cur.get('folder','/nonexistent')).name/'localization.json')
                if not loc.get('ready') or time.time()-loc.get('updated',0)>1 or loc.get('source_session')!=session or loc.get('map_id')!=selected.get('map_id'):raise ValueError('No verified RGB map transform')
                T=np.asarray(loc['transform']);a[:,:3]=a[:,:3]@T[:3,:3].T+T[:3,3]
            atomic(CACHE/'rgb-cloud.bin',a.tobytes());view['rgb_cloud']=dict(native,frame=target,map_id=selected.get('map_id') if target=='map' else None);rgb_tag=native['updated']
        except (OSError,ValueError,KeyError):pass
    try:
        if now-last_map>2:saved();last_map=now
        for key in ('grid','local'):
            m=pending.pop(key,None)
            if m and m.info.width*m.info.height<=16000000:
                a=np.array(m.data,dtype=np.float32).reshape(m.info.height,m.info.width)
                grid_file(a,key,dict(width=m.info.width,height=m.info.height,resolution=m.info.resolution,origin=origin(m.info.origin),frame=m.header.frame_id,session=session))
        for key in ('plan','route_plan'):
            m=pending.pop(key,None)
            if m is not None:view[key]=dict(frame=m.header.frame_id,points=[[p.pose.position.x,p.pose.position.y] for p in m.poses][::max(1,math.ceil(len(m.poses)/3000))],updated=time.time())
        m=pending.pop('footprint',None)
        if m:view['footprint']=dict(frame=m.header.frame_id,points=[[p.x,p.y] for p in m.polygon.points],updated=time.time())
        m=pending.get('cloud')
        if m and now-last_cloud>.5:
            pending.pop('cloud');last_cloud=now
            try:
                tf=buf.lookup_transform(target,m.header.frame_id,Time.from_msg(m.header.stamp));q=tf.transform.rotation;p=tf.transform.translation
                # Adapter's PointCloud2 layout is xyz float32, but validate before parsing.
                if m.point_step!=12 or m.height!=1:raise ValueError('Unexpected cloud layout')
                a=np.frombuffer(m.data,dtype='<f4').reshape(-1,3)[::max(1,math.ceil(m.width/20000))];a=a[np.isfinite(a).all(1)]
                a=(a@Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix().T+np.array([p.x,p.y,p.z])).astype('<f4')
                atomic(CACHE/'cloud.bin',a.tobytes());view['cloud']=dict(frame=target,count=len(a),updated=time.time(),session=session)
            except Exception:pass
        try:
            tf=buf.lookup_transform(target,'go2w_mppi_base',Time());q=tf.transform.rotation;p=tf.transform.translation
            stamp=tf.header.stamp.sec+tf.header.stamp.nanosec*1e-9
            if 0<=n.get_clock().now().nanoseconds*1e-9-stamp<.7:
                view['robot']=dict(frame=target,pose=[p.x,p.y,p.z,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))],updated=time.time())
        except Exception:pass
        view.pop('error',None)
    except Exception as e:view['error']=str(e)
    atomic(CACHE/'view.json',view)
n.create_timer(.25,tick)
try:rclpy.spin(n)
finally:n.destroy_node();rclpy.try_shutdown()
