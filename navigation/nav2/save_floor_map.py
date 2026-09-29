#!/usr/bin/env python3
"""Export a costmap snapshot for inspection. It is not an AMCL-ready relocalization pipeline."""
import json,time
from pathlib import Path
import numpy as np,rclpy,yaml
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
root=Path('/home/unitree/fast_livo2_port/build1');run=json.loads((root/'continuous_capture.json').read_text())['run'];out=root/run/'floor_costmap';out.mkdir(exist_ok=True)
rclpy.init();n=Node('floor_map_snapshot');maps=[];n.create_subscription(OccupancyGrid,'/global_costmap/costmap',lambda m:maps.append(m),1)
end=time.monotonic()+12
while not maps and time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.1)
if not maps:raise SystemExit('No fresh global map; snapshot failed')
m=maps[-1];a=np.asarray(m.data,dtype=np.int8).reshape(m.info.height,m.info.width);np.savez_compressed(str(out/'costmap.npz'),costs=a,resolution=m.info.resolution,origin=[m.info.origin.position.x,m.info.origin.position.y])
img=np.full(a.shape,205,dtype=np.uint8);img[a==0]=254;img[a>=99]=0
# Inflation values are kept in NPZ; PGM is a thresholded navigation costmap, not raw SLAM occupancy.
img[(a>0)&(a<99)]=254
with (out/'costmap.pgm').open('wb') as f:f.write(('P5\n%d %d\n255\n'%(m.info.width,m.info.height)).encode());f.write(img[::-1].tobytes())
(out/'costmap.yaml').write_text(yaml.safe_dump(dict(image='costmap.pgm',resolution=m.info.resolution,origin=[m.info.origin.position.x,m.info.origin.position.y,0.],negate=0,occupied_thresh=.65,free_thresh=.196)))
(out/'metadata.json').write_text(json.dumps(dict(mapping_run=run,frame=m.header.frame_id,saved_at=time.time(),note='Costmap snapshot only; same-session navigation. No relocalization installed.'),indent=2))
print(str(out));n.destroy_node();rclpy.shutdown()
