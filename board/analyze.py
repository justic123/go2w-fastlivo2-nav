#!/usr/bin/env python3
"""Summarize measured replay stages; never equate kernel speed with system speed."""
import argparse
import json
import math
from pathlib import Path
import statistics

def describe(values):
    values=sorted(values)
    if not values:return None
    return dict(count=len(values),mean=statistics.mean(values),median=statistics.median(values),
                p95=values[min(len(values)-1,math.ceil(.95*len(values))-1)],
                p99=values[min(len(values)-1,math.ceil(.99*len(values))-1)],max=values[-1])

def summarize(folder):
    events=[json.loads(s) for s in (folder/'observations.jsonl').read_text().splitlines()]
    profiles=[s['data'] for s in events if s['kind']=='profile']
    odom=[s['data'] for s in events if s['kind']=='odom']
    stages={};metrics={}
    for p in profiles:
        for name,value in p['stage_ms'].items():stages.setdefault(name,[]).append(value)
        for name,value in p['metrics'].items():
            if value is not None:metrics.setdefault(name,[]).append(value)
    sequence=[p['sequence'] for p in profiles]
    return dict(run=json.loads((folder/'run.json').read_text()),profile_count=len(profiles),odom_count=len(odom),
                sequence_gaps=sum(max(0,b-a-1) for a,b in zip(sequence,sequence[1:])),
                source_duration_s=odom[-1]['stamp']-odom[0]['stamp'] if len(odom)>1 else 0,
                stages_ms={k:describe(v) for k,v in stages.items()},metrics={k:describe(v) for k,v in metrics.items()})

def compare(first,second):
    def poses(folder):
        events=[json.loads(s) for s in (folder/'observations.jsonl').read_text().splitlines()]
        return {round(x['data']['stamp'],6):x['data']['pose'] for x in events if x['kind']=='odom'}
    a,b=poses(first),poses(second);common=sorted(set(a)&set(b));distance=[];rotation=[]
    for stamp in common:
        x,y=a[stamp],b[stamp]
        distance.append(math.sqrt(sum((u-v)**2 for u,v in zip(x[:3],y[:3]))))
        norm=math.sqrt(sum(v*v for v in x[3:])*sum(v*v for v in y[3:]))
        dot=abs(sum(u*v for u,v in zip(x[3:],y[3:]))/norm)
        rotation.append(2*math.acos(min(1.,dot)))
    return dict(matched_stamps=len(common),first_count=len(a),second_count=len(b),
                translation_m=describe(distance),rotation_rad=describe(rotation),
                note='Agreement with CPU is not independent ground-truth accuracy; unmatched stamps are reported.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folders',nargs='+',type=Path);a=p.parse_args()
    result=dict(runs=[summarize(x) for x in a.folders])
    if len(a.folders)==2:result['comparison']=compare(*a.folders)
    print(json.dumps(result,indent=2,allow_nan=False))
