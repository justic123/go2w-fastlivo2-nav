"""A timing message alone is insufficient to establish stationary localization."""
import math


class StationaryInitialization:
    def __init__(self):
        self.since=None;self.origin=None;self.first_count=None

    def observe(self, health, wall, monotonic):
        pose=health.get('pose')
        fresh=(health.get('ready') and 0<=wall-health.get('updated',0)<1 and
               isinstance(pose,list) and len(pose)==3 and all(math.isfinite(v) for v in pose) and
               health.get('odom_count',0)>0)
        if not fresh:
            self.since=None;self.origin=None;self.first_count=None;return False
        if self.since is None:
            self.since=monotonic;self.origin=pose;self.first_count=health['odom_count']
        if sum((a-b)**2 for a,b in zip(pose,self.origin))>.15**2:
            raise RuntimeError('Initialization moved/drifted >15cm; keep stationary and explicitly restart')
        return monotonic-self.since>=4 and health['odom_count']-self.first_count>=10
