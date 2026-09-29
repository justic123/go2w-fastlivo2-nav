#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
base=Path(sys.argv[1]); reports=[]
for root in sorted(base.glob('round-*')):
 rows=[json.loads(s) for s in (root/'lidar/messages.jsonl').read_text().splitlines()]
 manifest={}
 for r in rows:
  p=root/'lidar'/r['cdr_file'];raw=p.read_bytes();m=deserialize_message(raw,PointCloud2)
  assert m.width==r['width'] and m.height==r['height'] and len(m.data)==r['data_bytes']
  assert m.header.stamp.sec==r['stamp_sec'] and m.header.stamp.nanosec==r['stamp_nanosec']
  manifest[p.name]=hashlib.sha256(raw).hexdigest()
 assert len(manifest)==len(rows)==len(list((root/'lidar').glob('*.cdr')))
 (root/'cdr-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
 reports.append(dict(round=root.name,frames_verified=len(rows),total_bytes=sum(p.stat().st_size for p in (root/'lidar').glob('*.cdr'))))
(base/'full-capture-verification.json').write_text(json.dumps(reports,indent=2)+'\n')
print(json.dumps(reports,indent=2))
