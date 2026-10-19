"""Acceptance criteria for recorded-input fusion, independent of ROS."""
import math


def failures(events, seconds, max_age=.6):
    errors=[]
    odom=[e['data'] for e in events if e['kind']=='odom']
    lag=[e['data']['seconds'] for e in events if e['kind']=='lag']
    if any(e['kind']=='invalid' for e in events):errors.append('Observer rejected nonfinite data')
    if len(odom)<seconds*5:errors.append('Too few odometry outputs')
    if any(not all(math.isfinite(x) for x in d['pose']+[d['stamp']]) for d in odom):
        errors.append('Nonfinite pose or stamp')
    gaps=[b['stamp']-a['stamp'] for a,b in zip(odom,odom[1:])]
    if any(not 0<g<=max_age for g in gaps):errors.append('Odometry gap or nonincreasing stamp')
    if not lag or len(lag)<len(odom)*.9:errors.append('Missing processing lag observations')
    if any(not math.isfinite(x) or not 0<=x<=max_age for x in lag):errors.append('Processing lag outside source-age policy')
    return errors
