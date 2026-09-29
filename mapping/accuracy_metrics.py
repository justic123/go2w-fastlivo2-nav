#!/usr/bin/env python3
import json,sys,re
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);result=json.loads((root/'result.json').read_text());a=[json.loads(x) for x in (root/'odometry.jsonl').read_text().splitlines()]
t=np.array([x['stamp']-result['bag_start'] for x in a]);p=np.array([x['position'] for x in a]);q=np.array([x['quaternion_xyzw'] for x in a]);yaw=np.unwrap(np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2)))*180/np.pi
r={'ground_truth_available':False,'windows':{},'published':result['published'],'cloud_output':result.get('cloud_output'),'stop_reason':result['stop_reason']}
for lo,hi in [(5,10),(20,40),(62,74)]:
 m=(t>=lo)&(t<hi);pts=p[m];y=yaw[m]
 if len(pts):r['windows'][f'{lo}-{hi}']=dict(count=len(pts),axis_range_m=np.ptp(pts,axis=0).tolist(),position_jitter_p95_m=float(np.percentile(np.linalg.norm(pts-np.median(pts,axis=0),axis=1),95)),median_position=np.median(pts,axis=0).tolist(),median_yaw_deg=float(np.median(y)),yaw_range_deg=float(np.ptp(y)))
text=(root/'node.log').read_text(errors='replace');ts=np.array([float(x) for x in re.findall(r'Current Total Time\s*\|\s*([0-9.]+)',text)])
r['processing_block_ms']={'count':len(ts),'median':float(np.median(ts)*1000),'p95':float(np.percentile(ts,95)*1000),'max':float(ts.max()*1000)} if len(ts) else None
(root/'metrics.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
