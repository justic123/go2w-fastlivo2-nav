#!/usr/bin/env python3
"""Same-bag LIO/LIVO estimates, not ground-truth accuracy."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]/'evidence/motion-comparison'
origin=json.loads((root/'compare-gigabit-lio-01/result.json').read_text())['bag_start']
def read(name):
 r=[json.loads(x) for x in (root/name/'odometry.jsonl').read_text().splitlines()]
 t=np.array([x['stamp'] for x in r]);p=np.array([x['position'] for x in r]);q=np.array([x['quaternion_xyzw'] for x in r]);yaw=np.unwrap(np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2)))*180/np.pi
 return t-origin,p,yaw
lio=read('compare-gigabit-lio-01');livo=read('compare-gigabit-livo-01')
a=np.loadtxt(root.parent/'mapping/gigabit-visual-turn-01/trajectory.tum');q=a[:,4:8];live=(a[:,0]-origin,a[:,1:4],np.unwrap(np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2)))*180/np.pi)
result={'ground_truth_available':False,'time_origin':'source bag start','series':{},'differences':{}}
for name,(t,p,y) in [('LIO replay',lio),('LIVO replay',livo),('LIVO live',live)]:
 windows={}
 for lo,hi in [(5,10),(20,40),(62,74),(125,180)]:
  m=(t>=lo)&(t<hi);windows[f'{lo}-{hi}']=dict(count=int(m.sum()),median_position_m=np.median(p[m],axis=0).tolist(),median_yaw_deg=float(np.median(y[m])),position_axis_range_m=np.ptp(p[m],axis=0).tolist(),yaw_range_deg=float(np.ptp(y[m])))
 result['series'][name]=windows
for name,target in [('LIVO_minus_LIO',lio),('LIVO_replay_minus_live',live)]:
 t,p,y=livo;tt,pp,yy=target;m=(t>=max(t[0],tt[0]))&(t<=min(t[-1],tt[-1]));t=t[m];dp=p[m]-np.column_stack([np.interp(t,tt,pp[:,i]) for i in range(3)]);dy=y[m]-np.interp(t,tt,yy);d=np.linalg.norm(dp,axis=1)
 result['differences'][name]=dict(position_difference_median_m=float(np.median(d)),position_difference_p95_m=float(np.percentile(d,95)),position_difference_max_m=float(d.max()),yaw_difference_abs_p95_deg=float(np.percentile(abs(dy),95)))
(root/'gigabit_same_bag_comparison.json').write_text(json.dumps(result,indent=2))
f,ax=plt.subplots(3,1,figsize=(10,9),sharex=True)
for name,(t,p,y) in [('LIO replay',lio),('LIVO replay',livo),('LIVO live',live)]:
 ax[0].plot(t,p[:,0],label=name,alpha=.8);ax[1].plot(t,p[:,1],label=name,alpha=.8);ax[2].plot(t,y,label=name,alpha=.8)
for a,label in zip(ax,['X (m)','Y (m)','Yaw (degrees)']):a.set_ylabel(label);a.grid(alpha=.3)
ax[0].legend();ax[0].set_title('Same recorded inputs: estimates, not ground-truth errors');ax[-1].set_xlabel('Seconds since bag start');f.tight_layout();f.savefig(root/'gigabit_same_bag_comparison.png',dpi=150)
print(json.dumps(result,indent=2))
