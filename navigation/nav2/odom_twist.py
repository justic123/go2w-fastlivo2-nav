"""Measured planar twist from consecutive fused poses, including yaw wrap."""
import math
def yaw(q):
 x,y,z,w=q;return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
def planar_twist(previous,current):
 dt=current['stamp']-previous['stamp']
 if dt<=0:raise ValueError('Nonpositive odometry interval')
 p=current['pose'];old=previous['pose'];a=yaw(p[3:]);b=yaw(old[3:]);dx=(p[0]-old[0])/dt;dy=(p[1]-old[1])/dt
 return math.cos(a)*dx+math.sin(a)*dy,-math.sin(a)*dx+math.cos(a)*dy,math.atan2(math.sin(a-b),math.cos(a-b))/dt
