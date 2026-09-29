import csv,json,sys,numpy as np
from pathlib import Path
p=Path(sys.argv[1]);c=list(csv.DictReader((p/'camera.csv').open()));ref=int(c[0]['start_mono_ns'])*1e-9-10
out={};ticks_by_backend={}
for backend in ['ros','sdk']:
 r=list(csv.DictReader((p/(backend+'.csv')).open()));t=np.array([int(x['receive_monotonic_ns'])*1e-9-ref for x in r]);ticks=np.array([int(x['tick']) for x in r]);out[backend]={};ticks_by_backend[backend]=set(map(int,ticks))
 for name,a,b in [('before',1,9),('5hz',11,29),('between',32,39),('1hz',41,59),('after',62,70)]:
  x=ticks[(t>=a)&(t<b)];dt=np.diff(x);out[backend][name]={'n':len(x),'max_tick_gap_ms':int(dt.max()),'gaps_over_10ms':int((dt>10).sum()),'gaps_over_50ms':int((dt>50).sum())}
a,b=ticks_by_backend.values();lo=max(min(a),min(b));hi=min(max(a),max(b));out['same_ticks_in_common_interval']={x for x in a if lo<=x<=hi}=={x for x in b if lo<=x<=hi}
out['camera']={phase:{'count':sum(x['phase']==phase for x in c),'mean_request_ms':float(np.mean([(int(x['end_mono_ns'])-int(x['start_mono_ns']))/1e6 for x in c if x['phase']==phase]))} for phase in ['5hz','1hz']}
(p/'analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
