import csv,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);cols=['gx','gy','gz','ax','ay','az','qw','qx','qy','qz']
def load(p):
 r=list(csv.DictReader(p.open()));assert len(r)>100
 ticks=[int(x['tick']) for x in r];count=Counter(ticks);unique={t:v for t,v in zip(ticks,r) if count[t]==1}
 ts=np.array([int(x['receive_monotonic_ns']) for x in r]);gaps=np.diff(ts)/1e6
 return r,unique,dict(count=len(r),hz=float((len(r)-1)*1e9/(ts[-1]-ts[0])),max_gap_ms=float(gaps.max()),p99_gap_ms=float(np.percentile(gaps,99)),duplicates=len(ticks)-len(count),backwards=int(np.sum(np.diff(ticks)<0)))
a,au,ast=load(root/'sdk.csv');b,bu,bst=load(root/'ros/ros2.csv');keys=sorted(au.keys()&bu.keys());assert keys
av=np.array([[float(au[t][k]) for k in cols] for t in keys],dtype=np.float32);bv=np.array([[float(bu[t][k]) for k in cols] for t in keys],dtype=np.float32)
delta=np.array([int(bu[t]['receive_unix_ns'])-int(au[t]['receive_unix_ns']) for t in keys])/1e6
lo=max(min(au),min(bu));hi=min(max(au),max(bu));aa={int(x['tick']) for x in a if lo<=int(x['tick'])<=hi};bb={int(x['tick']) for x in b if lo<=int(x['tick'])<=hi}
d=dict(sdk=ast,ros2=bst,matched_unique_ticks=len(keys),float32_imu_vectors_equal=int(np.sum(np.all(av==bv,axis=1))),max_abs_difference=float(np.max(np.abs(av-bv))),unique_tick_overlap_range=[lo,hi],ticks_only_sdk=len(aa-bb),ticks_only_ros2=len(bb-aa),ros_minus_sdk_receipt_ms=dict(min=float(delta.min()),median=float(np.median(delta)),p99=float(np.percentile(delta,99)),max=float(delta.max())),ros_discovery=json.loads((root/'ros/summary.json').read_text()),note='Counts include unequal startup intervals; comparison uses overlapping ticks. Arrival timestamps are callback time, not hardware latency.')
def shared_stats(rows):
 rows=[r for r in rows if lo<=int(r['tick'])<=hi]
 tt=np.array([int(r['receive_monotonic_ns']) for r in rows]);tk=[int(r['tick']) for r in rows];dg=np.diff(tt)/1e6
 return dict(count=len(rows),max_gap_ms=float(dg.max()),p99_gap_ms=float(np.percentile(dg,99)),duplicate_ticks=len(tk)-len(set(tk)))
d['shared_interval']={'sdk':shared_stats(a),'ros2':shared_stats(b)}
(root/'comparison.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))
