#!/usr/bin/env python3
"""Export recorded CDR without assuming point-time units. ROS2 process only."""
import json,sys
from pathlib import Path
import numpy as np
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
src,out=map(Path,sys.argv[1:3]);out.mkdir(exist_ok=False)
rows=[json.loads(x) for x in (src/'lidar/messages.jsonl').read_text().splitlines()][:150]
dtype=np.dtype({'names':['x','y','z','intensity','ring','time'],'formats':['<f4','<f4','<f4','<f4','<u2','<f4'],'offsets':[0,4,8,12,16,18],'itemsize':22})
for i,r in enumerate(rows):
 m=deserialize_message((src/'lidar'/r['cdr_file']).read_bytes(),PointCloud2)
 assert m.point_step==22 and m.height==1 and not m.is_bigendian
 a=np.frombuffer(m.data,dtype=dtype,count=m.width)
 np.save(out/f'{i:04d}.npy',a)
(out/'frames.json').write_text(json.dumps(rows))
(out/'lowstate.csv').write_bytes((src/'lowstate.csv').read_bytes())
print('Exported',len(rows),'frames; original numeric point times preserved')
