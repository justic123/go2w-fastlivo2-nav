"""Bounded forward goal policy; no ROS or robot access."""
import math

def velocity(start,pose,distance=.3,max_speed=.05,hold_speed=False):
    if not .015<=max_speed<=.1:raise ValueError('invalid max speed')
    if not .1<=distance<=.5:raise ValueError('distance outside [0.1,0.5]m')
    if not all(math.isfinite(x) for x in (*start,*pose)):raise ValueError('nonfinite pose')
    x,y,yaw=pose;sx,sy,syaw=start
    dx,dy=x-sx,y-sy
    along=math.cos(syaw)*dx+math.sin(syaw)*dy
    cross=-math.sin(syaw)*dx+math.cos(syaw)*dy
    heading=math.atan2(math.sin(syaw-yaw),math.cos(syaw-yaw))
    if abs(cross)>.1 or abs(heading)>.2 or along<-.08 or along>distance+.1:raise ValueError('outside short forward corridor')
    # 起点朝向定义目标方向；不原地转向、不倒车补偿，越界直接失败。
    remaining=distance-along
    # 提前4cm请求停车以容纳控制/运动延迟；这不是实际精度承诺。
    if remaining<=.04:return 0.,0.,True
    return (max_speed if hold_speed else min(max_speed,max(.015,.4*remaining))),max(-.1,min(.1,.6*heading)),False


def endpoint_metrics(start, pose, distance):
    """SLAM-estimated endpoint in start frame; physical tape measurement stays separate."""
    if not all(math.isfinite(v) for v in (*start, *pose, distance)):
        raise ValueError('nonfinite endpoint')
    dx,dy=pose[0]-start[0],pose[1]-start[1]
    c,s=math.cos(start[2]),math.sin(start[2])
    along,cross=c*dx+s*dy,-s*dx+c*dy
    heading=math.atan2(math.sin(pose[2]-start[2]),math.cos(pose[2]-start[2]))
    return dict(along_m=along,cross_m=cross,signed_along_error_m=along-distance,
                goal_error_m=math.hypot(along-distance,cross),heading_error_deg=math.degrees(heading),
                source='SLAM estimate, not ground truth')
