"""Final yaw alignment; position drift requests a bounded, replanned recovery."""
import math

def wrap(x):return math.atan2(math.sin(x),math.cos(x))

class PositionRecoveryRequired(ValueError):
    pass

class TerminalAlignment:
    def __init__(self,target,yaw,now):
        self.target=target;self.yaw=yaw;self.started=now;self.phase='settling_position';self.samples=[]
    def step(self,pose,now):
        if now-self.started>35:raise ValueError('terminal alignment timeout')
        distance=math.hypot(pose[0]-self.target[0],pose[1]-self.target[1])
        if distance>.10:raise PositionRecoveryRequired('terminal position drift >10cm; replan position before further yaw')
        error=wrap(self.yaw-pose[2])
        if not self.samples or pose[3]!=self.samples[-1][3]:self.samples.append(pose)
        self.samples=[p for p in self.samples if pose[3]-p[3]<=1.2]
        stable=len(self.samples)>=5 and self.samples[-1][3]-self.samples[0][3]>=.8 and max(p[0] for p in self.samples)-min(p[0] for p in self.samples)<.03 and max(p[1] for p in self.samples)-min(p[1] for p in self.samples)<.03 and max(abs(wrap(p[2]-pose[2])) for p in self.samples)<.04
        if self.phase=='settling_position':
            if stable:
                if distance>.08:raise PositionRecoveryRequired('position outside 8cm after settling')
                self.phase='aligning_yaw';self.samples=[]
            elif now-self.started>6:raise ValueError('position did not settle within 6s')
            return (0.,0.,0.),False
        if abs(error)<=.10:
            self.phase='settling_yaw'
            if stable:
                if distance>.08:raise PositionRecoveryRequired('final position outside 8cm')
                return (0.,0.,0.),True
            return (0.,0.,0.),False
        if self.phase=='settling_yaw' and abs(error)<=.15:
            if stable:
                if distance>.08:raise PositionRecoveryRequired('final position outside 8cm')
                return (0.,0.,0.),True
            return (0.,0.,0.),False
        self.phase='aligning_yaw'
        return (0.,0.,math.copysign(min(.25,max(.08,.5*abs(error))),error)),False
