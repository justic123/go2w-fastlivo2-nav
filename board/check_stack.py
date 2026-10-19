#!/usr/bin/env python3
"""Bounded read-only co-load sampler. Does not start services or publish commands."""
import argparse
import json
from pathlib import Path
import statistics
import time

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=60);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not 10<=a.seconds<=180:raise SystemExit('seconds must be 10..180')
def read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}
fusion=read(root/'board/current.json');nav=read(root/'navigation/mppi/current.json')
if not fusion or not nav:raise SystemExit('Start fusion and navigation first')
selection=read(root/'navigation/mppi/selection.json')
f=Path(fusion['folder']);n=Path(nav['folder']);rows=[];end=time.monotonic()+a.seconds
while time.monotonic()<end:
    row=dict(wall=time.monotonic(),updated=time.time(),fusion=read(f/'health.json'),fusion_runtime=read(f/'runtime.json'),
             nav_input=read(n/'input.json'),nav_lifecycle=read(n/'lifecycle.json'),nav_runtime=read(n/'runtime.json'),temperatures_c={})
    if selection:row['localization']=read(n/'localization.json')
    # Files can be atomically updated during the reads; bracket freshness at the end.
    row['updated']=time.time()
    for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
        try:row['temperatures_c'][(zone/'type').read_text().strip()]=int((zone/'temp').read_text())/1000
        except OSError:pass
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):row['mem_available_mib']=int(line.split()[1])/1024
    rows.append(row);time.sleep(.2)
def percentiles(values):
    if not values:return None
    values=sorted(values)
    return dict(count=len(values),median=statistics.median(values),p95=values[min(len(values)-1,int(len(values)*.95))],maximum=max(values))
faults=[]
for row in rows:
    for key in ('fusion','nav_input','nav_lifecycle')+(('localization',) if selection else ()):
        data=row[key]
        if not data.get('ready') or not 0<=row['updated']-data.get('updated',0)<2:faults.append(dict(at=row['updated'],key=key,data=data))
    for key in ('fusion_runtime','nav_runtime'):
        if row[key].get('phase')!='running' or not 0<=row['updated']-row[key].get('updated',0)<2:faults.append(dict(at=row['updated'],key=key,data=row[key]))
    if selection:
        loc=row['localization']
        if loc.get('map_id')!=selection.get('map_id') or loc.get('source_session')!=fusion['run']:
            faults.append(dict(at=row['updated'],key='localization_identity',data=loc))
result=dict(seconds=a.seconds,source_session=fusion['run'],nav_folder=str(n),stationary_only=True,actuation_enabled=False,
            saved_map_id=selection.get('map_id'),
            passed=not faults,faults=faults,
            fusion_lag_s=percentiles([r['fusion']['lag_last_s'] for r in rows if r['fusion'].get('lag_last_s') is not None]),
            nav_pose_age_s=percentiles([r['nav_input']['pose_age_s'] for r in rows if r['nav_input'].get('pose_age_s') is not None]),
            fusion_output_hz=(rows[-1]['fusion'].get('odom_count',0)-rows[0]['fusion'].get('odom_count',0))/(rows[-1]['wall']-rows[0]['wall']),
            fusion_window_max_lag_s=max(r['fusion'].get('lag_max_s',0) or 0 for r in rows),
            nav_cloud_age_s=percentiles([r['nav_input']['cloud_age_s'] for r in rows if r['nav_input'].get('cloud_age_s') is not None]),
            max_cpu_temp_c=max((v for r in rows for k,v in r['temperatures_c'].items() if 'cpu' in k.lower()),default=None),
            min_available_memory_mib=min(r['mem_available_mib'] for r in rows),samples=rows)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','faults')},indent=2))
raise SystemExit(0 if result['passed'] else 1)
