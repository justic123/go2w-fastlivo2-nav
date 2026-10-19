#!/usr/bin/env python3
"""Read-only latency evidence; never opens sensor sockets or sends commands."""
import argparse,json,time,math
from pathlib import Path

def read(path):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return {}

def main():
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=120);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 if not 5<=args.seconds<=3600:raise ValueError('seconds must be 5..3600')
 root=Path(__file__).resolve().parents[1];nav=Path(read(root/'navigation/mppi/current.json')['folder']);fusion=Path(read(root/'board/current.json')['folder'])
 args.output.mkdir(parents=True,exist_ok=True);start=time.monotonic();values={};events=[];samples=0;bad=0;motion=False
 def add(name,v):
  if type(v) in (int,float) and math.isfinite(v):values.setdefault(name,[]).append(v)
 with (args.output/'samples.jsonl').open('w') as out:
  while time.monotonic()-start<args.seconds:
   now=time.time();i=read(nav/'input.json');l=read(nav/'localization.json');f=read(fusion/'health.json');imu=read(fusion/'bridge/imu_health.json');r=read(nav/'runtime.json')
   row=dict(t=now,input=i,localization=l,fusion=f,imu=imu,runtime=r);out.write(json.dumps(row)+'\n');samples+=1
   good=i.get('ready') and l.get('ready') and f.get('ready') and r.get('phase')=='running'
   if not good:bad+=1
   for key in ('pose_age_s','cloud_age_s'):add(key,i.get(key))
   for key,doc in [('input_status_age_s',i),('localization_status_age_s',l),('fusion_status_age_s',f)]:
    if doc.get('updated'):add(key,now-doc['updated'])
   add('fusion_lag_s',f.get('lag_last_s'));add('imu_source_age_s',imu.get('source_age_s'));add('clock_rate_ppm',imu.get('clock_rate_ppm'))
   add('icp_processing_s',l.get('stats',{}).get('processing_s'))
   for key,v in i.get('cloud_diagnostics',{}).items():add('cloud_'+key,v)
   if i.get('cloud_age_s',999)>.5 or not good:
    if len(events)<100:events.append(row)
   motion=motion or (nav/'motion_active').exists() or (nav/'route_active.json').exists()
   time.sleep(.05)
 def summary(v):
  v=sorted(v);return dict(n=len(v),min=v[0],p50=v[len(v)//2],p95=v[int((len(v)-1)*.95)],p99=v[int((len(v)-1)*.99)],max=v[-1],over_half_second=sum(x>.5 for x in v))
 data=dict(seconds=time.monotonic()-start,samples=samples,unhealthy_samples=bad,motion_marker_observed=motion,nav=str(nav),fusion=str(fusion),metrics={k:summary(v) for k,v in values.items()},last=row)
 (args.output/'summary.json').write_text(json.dumps(data,indent=2));(args.output/'events.json').write_text(json.dumps(events,indent=2));print(json.dumps({k:v for k,v in data.items() if k!='last'},indent=2))
if __name__=='__main__':main()
