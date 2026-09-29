"""Closed-loop initial path alignment; no translation before heading settles."""
import math

def wrap(x):return math.atan2(math.sin(x),math.cos(x))

def path_heading(points,pose,lookahead=.5):
 if len(points)<2:raise ValueError('No path for heading alignment')
 nearest=min(range(len(points)),key=lambda i:math.hypot(points[i][0]-pose[0],points[i][1]-pose[1]))
 for x,y in points[nearest:]:
  if math.hypot(x-pose[0],y-pose[1])>=lookahead:return math.atan2(y-pose[1],x-pose[0])
 x,y=points[-1]
 if math.hypot(x-pose[0],y-pose[1])<.08:return pose[2]
 return math.atan2(y-pose[1],x-pose[0])

class HeadingAlignment:
 def __init__(self,yaw,pose,now):
  self.yaw=yaw;self.start=pose;self.started=now;self.samples=[];self.phase='aligning_path'
 def step(self,pose,now):
  if now-self.started>30:raise ValueError('Initial heading alignment timeout')
  if math.hypot(pose[0]-self.start[0],pose[1]-self.start[1])>.4:raise ValueError('Initial turn translation exceeds 40cm; recheck route')
  error=wrap(self.yaw-pose[2])
  # Hysteresis avoids alternating translation/rotation near the heading threshold.
  if abs(error)<=.10 or (self.phase=='settling_path' and abs(error)<=.17):
   self.phase='settling_path'
   if not self.samples or pose[3]!=self.samples[-1][3]:self.samples.append(pose)
   self.samples=[p for p in self.samples if pose[3]-p[3]<=.8]
   stable=len(self.samples)>=4 and self.samples[-1][3]-self.samples[0][3]>=.4 and max(abs(wrap(p[2]-pose[2])) for p in self.samples)<.04 and max(p[0] for p in self.samples)-min(p[0] for p in self.samples)<.03 and max(p[1] for p in self.samples)-min(p[1] for p in self.samples)<.03
   return (0.,0.,0.),stable
  self.phase='aligning_path';self.samples=[]
  return (0.,0.,math.copysign(min(.5,max(.12,.7*abs(error))),error)),False
