"""Pure safety checks shared by live navigation and fault-injection tests."""
import math

def check_health(h, now):
    for key,limit in [('last_check',.3)]:
        if not math.isfinite(h.get(key,float('nan'))) or not 0<=now-h[key]<limit:
            raise ValueError('adapter heartbeat stale')
    for key,limit in [('pose_age_s',.85),('cloud_age_s',.8)]:
        v=h.get(key)
        if v is None or not math.isfinite(v) or not 0<=v<limit:
            raise ValueError(key+' stale')

def check_command(v, age):
    if len(v)!=3 or not all(math.isfinite(x) for x in (*v,age)):
        raise ValueError('nonfinite command')
    if not 0<=age<.35:raise ValueError('controller command stale')
    x,y,w=v
    if not 0<=x<=.10001 or abs(y)>1e-6 or abs(w)>.10001:
        raise ValueError('command outside limits')
    # No minimum-speed boost: preserve DWB collision-checked command.
    return min(x,.1),0.,max(-.1,min(.1,w))

def check_pose(prev, cur):
    if len(cur)!=4 or not all(math.isfinite(x) for x in cur):raise ValueError('invalid pose')
    if prev is not None:
        dt=cur[3]-prev[3]
        if dt<=0:raise ValueError('odometry timestamp rollback')
        if math.hypot(cur[0]-prev[0],cur[1]-prev[1])>.15:raise ValueError('odometry position jump')
        if abs(math.atan2(math.sin(cur[2]-prev[2]),math.cos(cur[2]-prev[2])))>.20:
            raise ValueError('odometry heading jump')

def swept_clear(grid, pose, command):
    """Conservative circular footprint over next 0.8s; unknown is blocked."""
    data,width,height,res,ox,oy=grid
    x,y,yaw=pose[:3];vx,_,w=command;radius=.60
    for k in range(5):
        if k:
            x+=vx*math.cos(yaw)*.2;y+=vx*math.sin(yaw)*.2;yaw+=w*.2
        lo_x=int(math.floor((x-radius-ox)/res));hi_x=int(math.floor((x+radius-ox)/res))
        lo_y=int(math.floor((y-radius-oy)/res));hi_y=int(math.floor((y+radius-oy)/res))
        for iy in range(lo_y,hi_y+1):
            for ix in range(lo_x,hi_x+1):
                if math.hypot(ox+(ix+.5)*res-x,oy+(iy+.5)*res-y)>radius+res*.71:continue
                if ix<0 or iy<0 or ix>=width or iy>=height:raise ValueError('footprint outside costmap')
                cost=data[iy*width+ix]
                if cost<0 or cost>=100:raise ValueError('footprint intersects unknown/lethal costmap')
