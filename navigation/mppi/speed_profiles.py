"""Explicit speed contracts; no motor calls and no implicit profile escalation."""
import json,math
from pathlib import Path
PROFILES={
 'baseline':dict(vx_max=.2,vx_min=-.1,wz_max=.8,accel=.2,decel=.3,pose_speed_limit=.5,vx_std=.12,prune_distance=1.7),
 'corridor04':dict(vx_max=.4,vx_min=-.1,wz_max=.8,accel=.2,decel=.4,pose_speed_limit=.7,vx_std=.18,prune_distance=1.7),
 'hall08':dict(vx_max=.8,vx_min=-.1,wz_max=.8,accel=.3,decel=.5,pose_speed_limit=1.1,vx_std=.3,prune_distance=2.5),
}
SOURCE_AGE_LIMITS={'baseline':.5,'corridor04':.6,'hall08':.3}
def profile(name):
 if name not in PROFILES:raise ValueError('Unknown speed profile: '+str(name))
 return dict(name=name,**PROFILES[name])

def source_age_limit(name):
 """Maximum source pose/cloud age in seconds for the selected speed contract."""
 return SOURCE_AGE_LIMITS[profile(name)['name']]
def selected(root):
 p=Path(root)/'speed_profile.json'
 return profile(json.loads(p.read_text())['name'] if p.exists() else 'baseline')
def from_config(p):
 c=p['controller_server']['ros__parameters']['FollowPath'];s=p['velocity_smoother']['ros__parameters']
 name=next((n for n,v in PROFILES.items() if c['vx_max']==v['vx_max']),None)
 q=profile(name)
 for value,expected in [(c['vx_min'],q['vx_min']),(c['wz_max'],q['wz_max']),(c['vy_max'],0.),(s['max_velocity'],[q['vx_max'],0.,q['wz_max']]),(s['min_velocity'],[q['vx_min'],0.,-q['wz_max']]),(s['max_accel'],[q['accel'],0.,.5]),(s['max_decel'],[-q['decel'],0.,-.5])]:
  if value!=expected:raise ValueError('Controller/smoother speed contract mismatch')
 return q
