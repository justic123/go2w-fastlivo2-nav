"""Pure safety checks shared by live navigation and fault-injection tests."""
import math
from heading_guard import check_heading

def check_health(h, now):
    for key,limit in [('last_check',.3)]:
        if not math.isfinite(h.get(key,float('nan'))) or not 0<=now-h[key]<limit:
            raise ValueError('adapter heartbeat stale')
    for key,limit in [('pose_age_s',.85),('cloud_age_s',.8)]:
        v=h.get(key)
        if v is None or not math.isfinite(v) or not 0<=v<limit:
            raise ValueError(key+' stale')

def check_command(v, age, max_forward=.1):
    if max_forward not in (.1,.2):raise ValueError("unsupported forward limit")
    if len(v)!=3 or not all(math.isfinite(x) for x in (*v,age)):
        raise ValueError('nonfinite command')
    if not 0<=age<.35:raise ValueError('controller command stale')
    x,y,w=v
    if not 0<=x<=max_forward+1e-9 or abs(y)>1e-6 or abs(w)>.8+1e-9:
        raise ValueError('command outside limits: vx=%r vy=%r yaw_rate=%r' % (x,y,w))
    # No minimum-speed boost: preserve DWB collision-checked command.
    return min(x,max_forward),0.,max(-.8,min(.8,w))

def check_pose(prev, cur, imu=None, level=False):
    if len(cur)!=4 or not all(math.isfinite(x) for x in cur):raise ValueError('invalid pose')
    if prev is not None:
        dt=cur[3]-prev[3]
        if dt<=0:raise ValueError('odometry timestamp rollback')
        if math.hypot(cur[0]-prev[0],cur[1]-prev[1])>.15:raise ValueError('odometry position jump')
        return check_heading(prev,cur,imu,level)

# User-measured outer wheel/leg envelope, centered on go2w_base for this trial.
# Includes 5 cm clearance on every side; keep Nav2 footprint + padding consistent.
HALF_LENGTH=.375+.05
HALF_WIDTH=.22+.05

def swept_clear(grid, pose, command):
    """Filled oriented rectangle over 2.0 s, including rotation and cell area."""
    data,width,height,res,ox,oy=grid
    x0,y0,yaw0=pose[:3];vx,_,w=command
    # Bound unsampled motion between 0.1 s samples using translational + corner speed.
    margin=(abs(vx)+math.hypot(HALF_LENGTH,HALF_WIDTH)*abs(w))*.05
    a,b=HALF_LENGTH+margin,HALF_WIDTH+margin;h=res/2
    for k in range(21):
        t=k*.1;yaw=yaw0+w*t
        if abs(w)>1e-9:
            x=x0+vx/w*(math.sin(yaw)-math.sin(yaw0))
            y=y0-vx/w*(math.cos(yaw)-math.cos(yaw0))
        else:x=x0+vx*t*math.cos(yaw0);y=y0+vx*t*math.sin(yaw0)
        c,s=math.cos(yaw),math.sin(yaw);ac,ass=abs(c),abs(s)
        rx=a*ac+b*ass;ry=a*ass+b*ac
        for iy in range(math.floor((y-ry-oy)/res),math.floor((y+ry-oy)/res)+1):
            for ix in range(math.floor((x-rx-ox)/res),math.floor((x+rx-ox)/res)+1):
                dx=ox+(ix+.5)*res-x;dy=oy+(iy+.5)*res-y
                # Separating axis theorem: robot rectangle versus full square cell.
                if abs(dx)>rx+h or abs(dy)>ry+h:continue
                if abs(c*dx+s*dy)>a+h*(ac+ass):continue
                if abs(-s*dx+c*dy)>b+h*(ac+ass):continue
                if ix<0 or iy<0 or ix>=width or iy>=height:raise ValueError('footprint outside costmap')
                cost=data[iy*width+ix]
                if cost<0 or cost>=100:raise ValueError('rectangular footprint intersects unknown/lethal costmap')
