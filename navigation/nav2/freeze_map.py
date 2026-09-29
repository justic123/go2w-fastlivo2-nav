#!/usr/bin/env python3
"""Save a fresh conservative costmap baseline, bound to this SLAM session."""
import json,time,os
from pathlib import Path
import numpy as np,rclpy,yaml
from nav_msgs.msg import OccupancyGrid
from mapping_session import current_mapping_run
root=Path('/home/unitree/fast_livo2_port/build1');session=current_mapping_run(root)
rclpy.init();node=rclpy.create_node('freeze_navigation_baseline');maps=[]
node.create_subscription(OccupancyGrid,'/global_costmap/costmap',lambda m:maps.append(m),10)
end=time.monotonic()+15
while time.monotonic()<end:
    rclpy.spin_once(node,timeout_sec=.2)
    if maps:
        msg=maps[-1];stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        # Foxy costmap publisher may leave header.stamp zero. Require two live publications
        # plus fresh adapter inputs instead of treating that header as acquisition time.
        health=json.loads(Path('/dev/shm/go2w_nav/adapter_status.json').read_text())
        fresh=0<=time.time()-health.get('last_check',0)<1 and 0<=health.get('pose_age_s',999)<.85 and 0<=health.get('cloud_age_s',999)<.8
        if len(maps)>=2 and fresh and (stamp==0 or 0<=time.time()-stamp<3):break
else:raise SystemExit('No fresh global costmap; nothing selected; received=%d age=%s topics=%s'%(len(maps),time.time()-stamp if maps else None,node.get_topic_names_and_types()))
if msg.header.frame_id!='camera_init' or session!=current_mapping_run(root):raise SystemExit('Map frame/session changed')
a=np.asarray(msg.data,dtype=np.int8).reshape(msg.info.height,msg.info.width)
if not np.any(a==0):raise SystemExit('No known free cells')
# Crop unknown margins, retaining the observed region plus a one-cell border.
ys,xs=np.where(a>=0);x0=max(0,int(xs.min())-1);y0=max(0,int(ys.min())-1)
a=a[y0:min(a.shape[0],ys.max()+2),x0:min(a.shape[1],xs.max()+2)]
out=root/'fixed_maps'/(session+'-'+str(time.time_ns()));out.mkdir(parents=True)
image=np.full(a.shape,205,dtype=np.uint8);image[(a>=0)&(a<100)]=254;image[a==100]=0
with (out/'map.pgm').open('wb') as f:
    f.write(('P5\n%d %d\n255\n'%(a.shape[1],a.shape[0])).encode());f.write(image[::-1].tobytes())
meta=dict(image='map.pgm',resolution=msg.info.resolution,origin=[msg.info.origin.position.x+x0*msg.info.resolution,msg.info.origin.position.y+y0*msg.info.resolution,0.0],negate=0,occupied_thresh=.65,free_thresh=.196)
(out/'map.yaml').write_text(yaml.safe_dump(meta));np.save(out/'source_costmap.npy',a)
selection=dict(mapping_run=session,yaml=str(out/'map.yaml'),saved_at=time.time(),note='Conservative costmap snapshot: only lethal value 100 retained as occupied; inflation recomputed. Same-session localization only.')
(out/'metadata.json').write_text(json.dumps(selection,indent=2))
tmp=root/'fixed_navigation_map.tmp';tmp.write_text(json.dumps(selection));os.replace(str(tmp),str(root/'fixed_navigation_map.json'))
print(json.dumps(selection));node.destroy_node();rclpy.shutdown()
