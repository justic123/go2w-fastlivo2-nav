#!/usr/bin/env python3
"""Read-only stationary measurement; never sends ROS goals or robot commands."""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np

def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))

def transformed_pose(v, transform):
    x, y, z, w = v[3:]
    n = x*x+y*y+z*z+w*w
    if abs(n-1) > .02:
        raise ValueError('Invalid orientation quaternion')
    # First column of body rotation suffices for heading; includes roll/pitch.
    forward = np.array([1-2*(y*y+z*z)/n, 2*(x*y+w*z)/n, 2*(x*z-w*y)/n])
    t = np.asarray(transform)
    xyz = t[:3,:3] @ v[:3] + t[:3,3]
    f = t[:3,:3] @ forward
    return [*map(float, xyz), math.atan2(f[1], f[0])]

def summarize(values):
    a = np.asarray(values)
    centre = np.median(a[:,:3], axis=0)
    yaw = math.atan2(np.sin(a[:,3]).mean(), np.cos(a[:,3]).mean())
    return dict(pose=[*map(float,centre),yaw],
                max_spread_m=float(np.max(np.linalg.norm(a[:,:3]-centre,axis=1))),
                max_heading_spread_deg=math.degrees(max(abs(wrap(v-yaw)) for v in a[:,3])))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--seconds',type=float,default=8)
    args=parser.parse_args()
    if not 3 <= args.seconds <= 60: parser.error('seconds must be within 3..60')
    root=Path(__file__).resolve().parent
    current=json.loads((root/'current.json').read_text())
    folder=Path(current['folder']); session=current['session']
    reference=json.loads(args.reference.read_text()) if args.reference else None
    samples=[]; stamps=set(); map_id=None
    until=time.monotonic()+args.seconds
    while time.monotonic()<until:
        if json.loads((root/'current.json').read_text()) != current:
            raise RuntimeError('Navigation session changed during measurement')
        d=json.loads((folder/'input.json').read_text())
        loc=json.loads((folder/'localization.json').read_text())
        if d.get('session')!=session or loc.get('source_session')!=session:
            raise RuntimeError('Input/localization session mismatch')
        for name,value in [('input',d),('localization',loc)]:
            age=time.time()-value['updated']
            if not value.get('ready') or not 0 <= age <= .7:
                raise RuntimeError(name+' not fresh/ready')
        if any(not -.05 <= d[k] <= .5 for k in ['pose_age_s','cloud_age_s']):
            raise RuntimeError('Source timestamps too old or in future')
        map_id=loc['map_id'] if map_id is None else map_id
        if map_id!=loc['map_id']: raise RuntimeError('Map changed')
        if reference and (reference['session']!=session or reference['map_id']!=map_id):
            raise RuntimeError('Reference belongs to a different session or map')
        stamp=d['pose']['stamp']
        if stamp not in stamps:
            stamps.add(stamp);v=d['pose']['pose']
            raw=transformed_pose(v,np.eye(4)); mapped=transformed_pose(v,loc['transform'])
            if not np.isfinite([*raw,*mapped]).all():raise RuntimeError('Nonfinite pose')
            samples.append(dict(stamp=stamp,raw=raw,map=mapped,transform=loc['transform'],
                pose_age_s=d['pose_age_s'],cloud_age_s=d['cloud_age_s'],localization_stats=loc.get('stats')))
        time.sleep(.1)
    if len(samples)<args.seconds*4:raise RuntimeError('Insufficient distinct samples')
    result=dict(label=args.label,session=session,map_id=map_id,created=time.time(),
        samples=samples,ground_truth='Operator measurement required; software differences are not physical accuracy')
    for frame in ['raw','map']:
        result[frame]=summarize([s[frame] for s in samples])
        if result[frame]['max_spread_m']>.025 or result[frame]['max_heading_spread_deg']>1.5:
            raise RuntimeError(frame+' pose not stationary/stable; measurement rejected')
        if reference:
            start=reference[frame]['pose'];now=result[frame]['pose']
            dx=now[0]-start[0];dy=now[1]-start[1];a=start[3]
            result[frame]['difference']=dict(x_m=dx,y_m=dy,xy_m=math.hypot(dx,dy),
                forward_m=math.cos(a)*dx+math.sin(a)*dy,left_m=-math.sin(a)*dx+math.cos(a)*dy,
                yaw_deg=math.degrees(wrap(now[3]-a)))
    target=folder/('repeatability-'+str(time.time_ns())+'.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(dict(file=str(target),**{k:v for k,v in result.items() if k!='samples'}),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
