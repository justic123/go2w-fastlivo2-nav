#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
p=Path(sys.argv[1]);s=json.loads((p/'bridge/summary.json').read_text());im=json.loads((p/'image_summary.json').read_text());log=(p/'node.log').read_text(errors='replace')
retr=[int(x) for x in re.findall(r'Retrieve (\d+) points from visual sparse map',log)]
jpeg=[(int(a),int(b)) for a,b in re.findall(r'status=(-?\d+) request_ms=(\d+)',(p/'jpeg.log').read_text())]
r=dict(bridge=s,image=im,vio_frames=len(retr),vio_frames_with_points=sum(x>0 for x in retr),retrieved_points_min=min(retr,default=0),retrieved_points_max=max(retr,default=0),visual_map_appends=len(re.findall(r'Append [1-9]\d* new visual map points',log)),ekf_timing_rows=log.count('computeJacobianAndUpdateEKF'),jpeg_calls=len(jpeg),jpeg_failed=sum(a!=0 for a,b in jpeg),max_request_ms=max((b for a,b in jpeg),default=0))
r['execution_pass']=s['failure'] is None and s['nonfinite_odometry']==0 and s['odometry_count']>=50 and im['published']>=50 and r['vio_frames_with_points']>=50
(p/'livo_result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if not r['execution_pass']:raise SystemExit(1)
