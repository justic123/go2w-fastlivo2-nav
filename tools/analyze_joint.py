#!/usr/bin/env python3
"""Analyze receipt-time overlap; never estimates hardware synchronization."""
import csv,json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1])
imu=list(csv.DictReader((root/'lowstate.csv').open()))
lidar=[json.loads(s) for s in (root/'lidar/messages.jsonl').read_text().splitlines()]
assert len(imu)>2 and len(lidar)>2, 'Insufficient sensor data'
def stats(x):
 x=np.asarray(x,dtype=float)
 return dict(min=float(x.min()),median=float(np.median(x)),p99=float(np.percentile(x,99)),max=float(x.max()))
it=np.array([int(x['receive_unix_ns']) for x in imu],dtype=np.int64)
lt=np.array([x['receive_unix_ns'] for x in lidar],dtype=np.int64)
h=np.array([x['stamp_sec']*10**9+x['stamp_nanosec'] for x in lidar],dtype=np.int64)
tick=np.array([int(x['tick']) for x in imu],dtype=np.int64)
a=np.array([[float(x[k]) for k in ['ax','ay','az']] for x in imu])
g=np.array([[float(x[k]) for k in ['gx','gy','gz']] for x in imu])
x=(tick-tick[0])/1000; y=(it-it[0])/1e9
slope,intercept=np.polyfit(x,y,1)
steps,counts=np.unique(np.diff(tick),return_counts=True)
summary=dict(
 note='Simultaneous receipt on same host. Not proof of hardware synchronization, units, calibration or stillness.',
 lidar=dict(count=len(lidar),receive_hz=(len(lt)-1)*1e9/(lt[-1]-lt[0]),header_gap_ms=stats(np.diff(h)/1e6),header_nonpositive=int(np.sum(np.diff(h)<=0)),receive_minus_header_ms=stats((lt-h)/1e6),points=stats([x['width']*x['height'] for x in lidar])),
 imu=dict(count=len(imu),receive_hz=(len(it)-1)*1e9/(it[-1]-it[0]),receive_gap_ms=stats(np.diff(it)/1e6),tick_steps_ms={str(k):int(v) for k,v in zip(steps,counts)},acc_norm=stats(np.linalg.norm(a,axis=1)),gyro_norm=stats(np.linalg.norm(g,axis=1)),acc_mean=a.mean(axis=0).tolist(),acc_std=a.std(axis=0).tolist(),gyro_std=g.std(axis=0).tolist(),receive_vs_tick_slope=float(slope),receipt_fit_residual_ms=stats((y-(slope*x+intercept))*1000)),
 receipt_overlap_seconds=max(0,min(it[-1],lt[-1])-max(it[0],lt[0]))/1e9,
 lidar_headers_inside_imu_receipt_interval=int(np.sum((h>=it[0])&(h<=it[-1]))))
q=np.array([[float(v[k]) for k in ['qw','qx','qy','qz']] for v in imu])
qn=np.linalg.norm(q,axis=1)
if np.all(qn > 0):
 q=q/qn[:,None]
 angle=np.degrees(2*np.arccos(np.clip(np.abs(q@q[0]),0,1)))
 summary['imu']['orientation_change_from_first_deg']=stats(angle)
summary['imu']['tick_backwards']=int(np.sum(np.diff(tick)<0))
summary['imu']['receive_gaps_over_10ms']=int(np.sum(np.diff(it)>10e6))
summary['imu']['nonfinite_values']=int(np.sum(~np.isfinite(np.concatenate([a.ravel(),g.ravel(),q.ravel()]))))
summary['lidar']['header_gaps_over_150ms']=int(np.sum(np.diff(h)>150e6))
point_stats=[r['point_stats'] for r in lidar if 'point_stats' in r]
summary['lidar']['frames_with_checked_point_schema']=len(point_stats)
if point_stats:
 summary['lidar']['point_time_max_raw']=stats([p['time_max'] for p in point_stats])
 summary['lidar']['point_time_min_raw']=stats([p['time_min'] for p in point_stats])
 summary['lidar']['point_time_decreases_per_frame']=stats([p['time_decreases'] for p in point_stats])
 summary['lidar']['nonfinite_xyz_time']=sum(p['nonfinite'] for p in point_stats)
 summary['lidar']['ring_range']=[min(p['ring_min'] for p in point_stats),max(p['ring_max'] for p in point_stats)]
(root/'analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
