"""Do not reset DWB critics for geometrically unchanged stationary replans."""
import math

def needs_refresh(candidate, active, pose, accepted_pose):
    if math.hypot(pose[0]-accepted_pose[0],pose[1]-accepted_pose[1])>=.2:return True
    if len(active)<2:return True
    def distance(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0.
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    return any(min(distance(p,a,b) for a,b in zip(active,active[1:]))>.15 for p in candidate)
