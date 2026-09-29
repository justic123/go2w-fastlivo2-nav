"""Mapping may catch up briefly; navigation keeps its independent strict age checks."""
import math
class BacklogGuard:
 def __init__(self,soft=1.,hard=3.,grace=5.):
  self.soft,self.hard,self.grace=soft,hard,grace;self.since=None
 def check(self,age,now):
  if not math.isfinite(age) or age<-.1:raise RuntimeError('Invalid/future source timestamp: '+str(age))
  if age>=self.hard:raise RuntimeError('Mapping backlog hard limit exceeded: '+str(age))
  if age>self.soft:
   if self.since is None:self.since=now
   if now-self.since>=self.grace:raise RuntimeError('Mapping backlog persisted beyond recovery window: '+str(age))
   return 'catching_up'
  self.since=None;return 'live'
