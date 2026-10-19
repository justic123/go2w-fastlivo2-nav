"""Map-owned physical references: provide a prior, never force a map transform.

Call mutations under console.lock. No motion commands; all recoveries still pass
multi-start scan matching and the live localization validator.
"""
import hashlib,math,time,uuid
from map_store import map_path

FILE='localization_anchors.json'
BLOCKED={'mapping','starting','validating_map','recovering'}

def entries(c,ident):
    path=map_path(c,ident)/FILE
    if path.is_symlink():raise ValueError('固定定位点文件不能为链接')
    if not path.exists():return {}
    data=c.read(path)
    if data.get('schema')!=1 or data.get('map_id')!=ident or not isinstance(data.get('anchors'),dict):
        raise ValueError('固定定位点文件与地图不一致')
    return data['anchors']

def geometry(c,ident):
    # Only on save/use, never hash the point cloud in the web status polling loop.
    h=hashlib.sha256();root=map_path(c,ident)
    for filename in ('map.yaml','map.pgm','points.npy'):
        path=root/filename
        if path.is_symlink():raise ValueError('地图文件不能为链接')
        h.update(filename.encode())
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def context(c):
    c.assert_no_motion();d=c.state();ident=d.get('map_id')
    if not ident or d.get('phase') in BLOCKED:raise ValueError('请先选择已保存地图并结束当前操作')
    map_path(c,ident)
    return d,ident

def store(c,ident,anchors):
    c.write(map_path(c,ident)/FILE,dict(schema=1,map_id=ident,anchors=anchors))

def checked_pose(value):
    if not isinstance(value,list) or len(value)!=7 or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):
        raise ValueError('固定定位点三维位姿无效')
    if abs(sum(x*x for x in value[3:])-1)>.02:raise ValueError('固定定位点朝向无效')
    return value

def capture(c,name):
    d,ident=context(c)
    if d.get('phase')!='navigation':raise ValueError('先完成定位，再保存固定定位点')
    c.check_session(d);c.health();items=entries(c,ident)
    if name in items:raise ValueError('固定定位点同名，请换名；要重新标定请先删除旧点')
    if len(items)>=100:raise ValueError('每张地图最多100个固定定位点')
    signature=geometry(c,ident);r=c.folder();output=r/'localization_anchor_capture.json'
    if output.exists():output.unlink()
    started=time.time()
    c.run(['docker','exec','go2w-nav2-mppi','bash','-c',
           'source /opt/ros/humble/setup.bash; exec python3 /work/record.py --anchor -- "$1"','_',name],15)
    t=c.read(output);c.check_session(d);c.health()
    if c.state().get('map_id')!=ident or t.get('map_id')!=ident or t.get('source_session')!=d.get('session') or t.get('frame')!='map':
        raise ValueError('采样期间地图或会话变化，未保存固定点')
    if not started<=t.get('created',0)<=time.time() or t.get('source')!='stationary_fused_pose' or t.get('samples',0)<15:
        raise ValueError('固定点采样无效或过期')
    if signature!=geometry(c,ident):raise ValueError('地图内容已变化，未保存固定点')
    checked_pose(t.get('map_pose'))
    items[name]=dict(t,name=name,version=uuid.uuid4().hex,geometry=signature)
    store(c,ident,items)
    print('固定定位点已保存：'+name+'。请保留地面位置和机头朝向标记；导航目标和路线未改动。',flush=True)

def selected(c,ident,name,version):
    items=entries(c,ident);anchor=items.get(name)
    if not anchor or not version or anchor.get('version')!=version:raise ValueError('固定定位点已变化或不存在，请刷新后重选')
    if anchor.get('map_id')!=ident or anchor.get('frame')!='map':raise ValueError('固定定位点不属于当前地图')
    return items,anchor

def remove(c,name,version):
    _,ident=context(c);items,_=selected(c,ident,name,version);del items[name];store(c,ident,items)
    print('固定定位点已删除；地图和导航目标保留。',flush=True)

def restore(c,name,version):
    _,ident=context(c);_,anchor=selected(c,ident,name,version)
    if anchor.get('geometry')!=geometry(c,ident):raise ValueError('地图内容已变化，请重新标定固定定位点')
    p=checked_pose(anchor.get('map_pose'))
    print('使用固定定位点 '+name+' 作为初值；请保持静止，仍须雷达匹配通过，不会运动。',flush=True)
    recover_hint(c,p)

def recover_hint(c,map_pose):
    d,ident=context(c);checked_pose(map_pose)
    for t in d.get('points',{}).values():
        if t.get('map_id')!=ident or t.get('frame')!='map':raise ValueError('导航目标不属于当前地图')
    try:
        c.prepare_assisted_inputs();r=c.folder();inp=c.read(r/'input.json');c.health(False)
        session=c.desk()['run']
        if inp['session']!=session:raise ValueError('输入会话变化')
        candidate_path=r/'registration_candidate.json'
        if candidate_path.exists():candidate_path.unlink()
        c.write(r/'initial_pose.json',dict(map_id=ident,source_session=session,created=time.time(),map_pose=map_pose,odom_pose=inp['pose']['pose']))
        c.run(['docker','exec','go2w-nav2-mppi','bash','-c','source /opt/ros/humble/setup.bash; exec python3 /work/capture_local.py'],30)
        c.run(['docker','exec','go2w-nav2-mppi','python3','/work/relocalize.py','--map-id',ident,'--hint'],180)
        candidate=c.read(candidate_path);c.validate_registration(candidate,ident,session);c.health(False)
        c.activate_registration(d,candidate,session)
    except BaseException as e:
        c.save(phase='recovery_failed',preview=None,route_preview=None,recovery_error=str(e) or '操作已取消');raise
