"""Time-aware heading continuity with a conservative IMU-gated extension.

The 1.2 rad/s envelope is a trial bound (1.5 times the command cap), not a
manufacturer physical limit. Larger-than-legacy increments require level-body
IMU z integration. Missing evidence never authorizes a larger increment.
"""
import math
MAX_DT=.25
RATE_ENVELOPE=1.2
ANGLE_SLACK=.04
HARD_ANGLE=.35
IMU_RESIDUAL=.04

def imu_delta(samples,start,end):
    # Samples: [sensor_stamp, gx, gy, gz], rad/s, same board sensor clock.
    if len(samples)<2:raise ValueError('IMU history unavailable')
    if any(len(s)!=4 or not all(math.isfinite(v) for v in s) for s in samples):
        raise ValueError('invalid IMU history')
    if samples[0][0]>start or samples[-1][0]<end:raise ValueError('IMU does not cover pose interval')
    total=0.;covered=0.
    for a,b in zip(samples,samples[1:]):
        dt=b[0]-a[0]
        if dt<=0:raise ValueError('IMU history rollback')
        lo,hi=max(start,a[0]),min(end,b[0])
        if hi<=lo:continue
        if dt>.020001:raise ValueError('IMU interval gap')
        if max(abs(a[3]),abs(b[3]))>1.5:raise ValueError('IMU turn rate exceeds trial envelope')
        z0=a[3]+(b[3]-a[3])*(lo-a[0])/dt
        z1=a[3]+(b[3]-a[3])*(hi-a[0])/dt
        total+=(z0+z1)*.5*(hi-lo);covered+=hi-lo
    if abs(covered-(end-start))>1e-6:raise ValueError('IMU coverage incomplete')
    return total

def check_heading(previous,current,imu=None,level=False):
    dt=current[3]-previous[3]
    if dt<=0:raise ValueError('odometry timestamp rollback')
    if dt>MAX_DT:raise ValueError('odometry interval >250ms')
    delta=math.atan2(math.sin(current[2]-previous[2]),math.cos(current[2]-previous[2]))
    bound=min(HARD_ANGLE,ANGLE_SLACK+RATE_ENVELOPE*dt)
    if abs(delta)>bound:raise ValueError('odometry heading rate jump: dt=%.6f delta=%.6f bound=%.6f'%(dt,delta,bound))
    if abs(delta)>.20:
        if not level:raise ValueError('large heading increment requires level-body IMU verification')
        observed=imu_delta(imu or [],previous[3],current[3])
        if abs(delta-observed)>IMU_RESIDUAL:raise ValueError('odometry/IMU heading disagreement')
        return dict(dt=dt,delta=delta,bound=bound,imu_delta=observed,residual=delta-observed)
    return None

def is_level(q):
    x,y,z,w=q
    roll=math.atan2(2*(w*x+y*z),1-2*(x*x+y*y))
    pitch=math.asin(max(-1.,min(1.,2*(w*y-z*x))))
    return abs(roll)<=.10 and abs(pitch)<=.10
