"""Pause action eligibility while retaining read-only inputs and localization."""
class RuntimeHealth:
    def __init__(self,stable_seconds=1.):
        self.stable_seconds=stable_seconds;self.degraded=False;self.good_since=None
    def observe(self,now,problem):
        if problem:
            self.degraded=True;self.good_since=None
            return 'degraded',problem
        if self.degraded:
            if self.good_since is None:self.good_since=now
            if now-self.good_since<self.stable_seconds:return 'degraded','Waiting for stable fresh localization and inputs'
        self.degraded=False;return 'running',None
