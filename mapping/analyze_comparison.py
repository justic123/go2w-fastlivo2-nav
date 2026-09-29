#!/usr/bin/env python3
import json,sys,re,math
from pathlib import Path
root=Path(sys.argv[1]);results=[]
for p in sorted(root.glob('replay-motion-*')):
 if not (p/'result.json').exists():continue
 r=json.loads((p/'result.json').read_text());rows=[json.loads(x) for x in (p/'odometry.jsonl').read_text().splitlines()]
 r['run']=p.name;r['first_crossing_seconds_from_bag_start']={}
 for lim in [.1,1,5,10,20]:
  a=next((a for a in rows if a['radius']>lim),None)
  r['first_crossing_seconds_from_bag_start'][str(lim)]=a['stamp']-r['bag_start'] if a else None
 log=(p/'node.log').read_text(errors='replace')
 r['zero_effective_feature_log_lines']=len(re.findall(r'effective feature num: 0\b',log))
 r['imu_sync_warning_lines']=log.count('IMU and LiDAR not synced')
 r['estimated_path_length_m']=sum(math.dist(a['position'],b['position']) for a,b in zip(rows,rows[1:]))
 results.append(r)
(root/'comparison.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
