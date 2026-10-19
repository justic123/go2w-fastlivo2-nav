#!/usr/bin/env python3
"""Fixed web action adapter. All movement uses the existing protected executor."""
import fcntl,json,sys,time,math
from pathlib import Path
from common import ROOT,pose,name
sys.path.insert(0,str(ROOT/'demo'))
import console as c
import mission
import map_store
import localization_anchors

def run(req):
    action=req['action']
    if action=='stop':c.stop_motion();return
    with (ROOT/'demo/console.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('交互菜单或其他操作正在占用控制权，请先退出旧菜单')
        if action not in ('navigate','route-execute','route-resume'):c.assert_no_motion()
        if action in ('start','finish','restore','assist','anchor-save','anchor-use') and req.get('stationary') is not True:raise ValueError('请先确认机器狗静止')
        if action in ('navigate','route-execute','route-resume') and req.get('confirm_motion') is not True:raise ValueError('请明确确认实际运动')
        if action in ('anchor-save','anchor-use','anchor-delete','assist','map-point','navigate','preview','record','route-set','route-preview','route-execute','route-resume-preview','route-resume','point-settings'):
            if req.get('map_id')!=c.state().get('map_id'):raise ValueError('页面地图已变化，请刷新后重试')
        if action in ('record','map-point'):
            from motion_modes import point_fingerprint
            old=c.state().get('points',{}).get(name(req['name']))
            expected=req.get('replace_fingerprint')
            if old is not None and (not expected or expected!=point_fingerprint(old)):
                raise ValueError('同名点已存在或已变化，请重新确认覆盖，原点未改动')
            if old is None and expected:
                raise ValueError('原目标已不存在，请刷新后新建')
        if action in ('record','map-point','point-settings'):
            from motion_modes import action_choice,manual_handoff
            chosen=action_choice(req.get('arrival_motion','keep'))
            if 'manual_handoff' in req:manual_handoff(req)
        if action in ('restore','assist') and c.state().get('phase')=='navigation' and c.service_problem() is None:
            raise ValueError('当前地图定位已就绪，无需重复重定位；可直接记录目标或预演')
        if action=='delete-map':
            if req.get('confirm_delete') is not True:raise ValueError('请确认将地图移入回收站')
            map_store.delete(c,req.get('name'),req.get('map_version'))
        elif action=='restore-map':map_store.restore(c,req.get('trash_id'))
        elif action=='start':c.start_mapping()
        elif action=='finish':c.finish_mapping()
        elif action=='load-map':
            if req['name']==c.state().get('map_id') and c.service_problem() is None:
                print('当前地图已加载且定位正常，保留现有定位。',flush=True)
            else:c.load_map(req['name'])
        elif action=='restore':c.restore()
        elif action=='anchor-save':localization_anchors.capture(c,name(req['name']))
        elif action=='anchor-use':
            if req.get('confirm_placement') is not True:raise ValueError('请确认已放回固定标记并对齐朝向')
            localization_anchors.restore(c,name(req['name']),req.get('anchor_version'))
        elif action=='anchor-delete':
            if req.get('confirm_delete') is not True:raise ValueError('请确认删除固定定位点')
            localization_anchors.remove(c,name(req['name']),req.get('anchor_version'))
        elif action=='record':
            n=name(req['name']);c.record(n);c.point_settings.edit(c,n,req.get('arrival_motion','keep'),req.get('manual_handoff',False))
        elif action=='point-settings':c.point_settings.edit(c,name(req['name']),req.get('arrival_motion','keep'),req.get('manual_handoff'))
        elif action=='preview':c.preview(name(req['name']))
        elif action=='navigate':c.navigate(name(req['name']))
        elif action=='route-set':
            names=req.get('names')
            if not isinstance(names,list) or (len(names)!=0 and not 2<=len(names)<=50):raise ValueError('路线需2–50个点；空列表用于清空路线')
            from route_model import route_spec
            d=c.state();ordered=[name(n) for n in names]
            if not d.get('map_id') or d.get('phase') in ('mapping','starting','validating_map'):raise ValueError('请先保存或选择地图')
            if ordered:route_spec(d,ordered)
            c.save(route=dict(names=ordered,mode='stop_at_each'),route_preview=None)
            c.write(c.MPPI/'maps'/d['map_id']/'console_points.json',dict(points=d['points'],selected=d.get('selected'),route=c.state()['route']))
        elif action=='route-preview':mission.preview(c)
        elif action=='route-execute':
            stopped=mission.resume_status(c)
            if stopped.get('available') and req.get('restart_token')!=stopped['token']:
                raise ValueError('已有停止任务。请用“预演剩余路线→继续未完成任务”；如需从头重启，请刷新后明确确认重新执行')
            mission.execute(c)
        elif action in ('route-resume-preview','route-resume'):
            if not isinstance(req.get('resume_token'),str) or not req['resume_token']:raise ValueError('缺少当前停止任务标识，请刷新后重试')
            (mission.preview if action=='route-resume-preview' else mission.execute)(c,resume=True,expected_token=req['resume_token'])
        elif action=='map-point':
            d=c.state();p=pose(req['pose']);n=name(req['name'])
            if not d.get('map_id') or d['phase'] in ('mapping','starting','validating_map'):raise ValueError('请先保存或选择地图')
            from motion_modes import arrival_motion
            target=dict(name=n,frame='map',map_id=d['map_id'],source_session=d.get('session'),pose=p,created=time.time(),source='web_map_click',ground_truth=None,arrival_motion=chosen)
            target['manual_handoff']=manual_handoff(req)
            d['points'][n]=target;d.update(selected=n,preview=None,route_preview=None);c.write(c.STATE,d)
            c.write(c.MPPI/'maps'/d['map_id']/'console_points.json',dict(points=d['points'],selected=n,route=d.get('route')))
            print('目标已保存；尚未发送运动指令。',flush=True)
        elif action=='assist':
            p=pose(req['pose'])
            localization_anchors.recover_hint(c,[p[0],p[1],0.,0.,0.,math.sin(p[2]/2),math.cos(p[2]/2)])
        else:raise ValueError('不支持的操作')

if __name__=='__main__':
    try:run(json.load(sys.stdin))
    except BaseException as e:print('操作未完成：'+(str(e) or '已取消'),flush=True);sys.exit(1)
