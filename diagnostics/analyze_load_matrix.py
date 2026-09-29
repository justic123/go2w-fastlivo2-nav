import csv,json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);results={}
def read(p,fields=('receive_monotonic_ns','tick')):
 r=list(csv.DictReader(p.open()));return {int(x['tick']):x for x in r},r
def stats(rows):
 ticks=np.array([int(r['tick']) for r in rows]);d=np.diff(ticks);rt=np.diff([int(r['receive_monotonic_ns']) for r in rows])/1e6
 return {'rows':len(rows),'max_tick_gap_ms':int(d.max()),'gaps_over_10ms':int((d>10).sum()),'gaps_over_50ms':int((d>50).sum()),'max_receipt_gap_ms':float(rt.max()),'duplicates':int((d==0).sum()),'tick_span_ms':int(ticks[-1]-ticks[0])}
for name in ['idle','lidar','algorithm','display']:
 p=root/name
 if not (p/'ros.csv').exists():continue
 a,aa=read(p/'ros.csv');b,bb=read(p/'sdk.csv');lo=max(min(a),min(b));hi=min(max(a),max(b));ar={k for k in a if lo<=k<=hi};br={k for k in b if lo<=k<=hi};match=sorted(ar&br)
 r={'ros':stats([x for x in aa if lo<=int(x['tick'])<=hi]),'sdk':stats([x for x in bb if lo<=int(x['tick'])<=hi]),'ticks_only_ros':len(ar-br),'ticks_only_sdk':len(br-ar)}
 delta=np.array([int(a[k]['receive_monotonic_ns'])-int(b[k]['receive_monotonic_ns']) for k in match])/1e6;r['ros_minus_sdk_ms_median_p99']=np.quantile(delta,[.5,.99]).tolist()
 cols=['gx','gy','gz','ax','ay','az'];r['matched_values_equal']=all(all(np.float32(a[k][c])==np.float32(b[k][c]) for c in cols) for k in match)
 def net(file):
  lines=file.read_text().splitlines();idx=next(i for i,x in enumerate(lines) if x.startswith('Udp:'));return dict(zip(lines[idx].split()[1:],map(int,lines[idx+1].split()[1:])))
 if (p/'net_after.txt').exists():
  n0=net(p/'net_before.txt');n1=net(p/'net_after.txt');r['udp_counter_delta']={k:n1[k]-n0[k] for k in n0}
 bridge=p/'bridge_timing.csv'
 if bridge.exists():
  rows=list(csv.DictReader(bridge.open()));ticks=[int(x['tick']) for x in rows];u=set(ticks);lo=max(min(u),min(a),min(b));hi=min(max(u),max(a),max(b));u={x for x in u if lo<=x<=hi};ar={x for x in a if lo<=x<=hi};br={x for x in b if lo<=x<=hi};r['bridge']={'max_tick_gap_ms':max(np.diff(ticks)).item(),'monitor_ros_ticks_missing_from_bridge':len(ar-u),'monitor_sdk_ticks_missing_from_bridge':len(br-u),'bridge_ticks_missing_from_monitor_ros':len(u-ar)}
 results[name]=r
(root/'analysis.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
