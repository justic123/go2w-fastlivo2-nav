"""Post-stop verification only. Never emits motion or retries a navigation goal."""
import math

def stationary_report(samples, span=1.5):
    # Include one sample just before the window boundary: at 5 Hz a hard
    # '8 within 1.5s' requirement rejects healthy jittered streams.
    out=dict(stationary=False,samples=0,span_s=0.,reason='停车后采样不足')
    if len(samples)<2:return out
    if any(len(p)<4 or not all(math.isfinite(v) for v in p[:4]) for p in samples):return dict(out,reason='位姿数值无效')
    if any(b[3]<=a[3] for a,b in zip(samples,samples[1:])):return dict(out,reason='位姿时间未递增')
    last=samples[-1];cut=last[3]-span;start=0
    for i,p in enumerate(samples):
        if p[3]<=cut:start=i
        else:break
    recent=samples[start:];duration=last[3]-recent[0][3]
    gaps=[b[3]-a[3] for a,b in zip(recent,recent[1:])]
    xy=max(math.hypot(p[0]-last[0],p[1]-last[1]) for p in recent)
    turn=max(abs(math.atan2(math.sin(p[2]-last[2]),math.cos(p[2]-last[2]))) for p in recent)
    out.update(samples=len(recent),span_s=duration,max_gap_s=max(gaps,default=0),xy_spread_m=xy,yaw_spread_rad=turn)
    if duration<span or len(recent)<6:return out
    if max(gaps,default=0)>.4:return dict(out,reason='停车后位姿采样中断')
    if xy>.025 or turn>.025:return dict(out,reason='停车后位置或朝向仍有变化')
    return dict(out,stationary=True,reason=None)

def verify_stop(pump, healthy, samples, clock, timeout=6.):
    start=clock();last=None;after_stamp=float('-inf');health_retries=0;last_health_error=None
    while clock()-start<timeout:
        pump()
        try:healthy()
        except (RuntimeError,ValueError) as error:
            # Transport is already closed. Wait for a NEW healthy stationary
            # window, never resume control or accept the old stale samples.
            rows=samples()
            if rows:after_stamp=rows[-1][3]
            health_retries+=1;last_health_error=str(error)
            last=dict(stationary=False,reason='等待停车后的新鲜定位：'+str(error))
            continue
        last=stationary_report([p for p in samples() if p[3]>after_stamp])
        if last['stationary']:return dict(last,wait_s=clock()-start,health_retries=health_retries,last_health_error=last_health_error)
    return dict(last or stationary_report([]),wait_s=clock()-start,health_retries=health_retries,last_health_error=last_health_error)

def completion_issues(result):
    issues=[]
    if result.get('reason'):issues.append(result['reason'])
    if result.get('navigation_status')!=4:issues.append('导航动作尚未成功到达')
    if result.get('guard_stop',{}).get('stop_code')!=0:issues.append('停车指令未确认成功')
    if result.get('final_health_error'):issues.append('停车后定位/输入校验失败：'+result['final_health_error'])
    if not result.get('stationary_after_stop'):issues.append('未确认停稳：'+result.get('stop_verification',{}).get('reason','有效静止位姿不足'))
    for key,limit,label,unit,scale in [('estimated_xy_error',.08,'位置误差','厘米',100),('estimated_yaw_error',.12,'朝向误差','度',180/math.pi)]:
        v=result.get(key)
        if v is None or not math.isfinite(v):issues.append(label+'未取得')
        elif v>limit:issues.append('%s %.1f%s，超过 %.1f%s'%(label,v*scale,unit,limit*scale,unit))
    return list(dict.fromkeys(issues))
