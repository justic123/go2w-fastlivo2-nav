"""Recoverable map removal. Called under the console lock, never during motion."""
import hashlib,json,time,uuid
from pathlib import Path

def safe_id(value):
    if not isinstance(value,str) or not value or value in ('.','..') or Path(value).name!=value or '/' in value or '\\' in value:
        raise ValueError('地图标识无效')
    return value

def map_path(c,ident):
    p=c.MPPI/'maps'/safe_id(ident)
    if p.is_symlink() or not p.is_dir():raise ValueError('地图不存在或为不支持的链接')
    return p

def version(c,ident):
    p=map_path(c,ident);data=[]
    for n in ('map.yaml','map.pgm','points.npy','metadata.json','console_points.json','localization_anchors.json'):
        f=p/n
        if f.is_symlink():raise ValueError('地图文件不能为链接')
        if f.exists():
            s=f.stat();data.append((n,s.st_ino,s.st_size,s.st_mtime_ns))
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()

def trash_entries(c):
    out=[]
    for p in (c.MPPI/'maps-trash').glob('*/receipt.json'):
        try:
            d=c.read(p)
            if not p.parent.is_symlink() and (p.parent/'map').is_dir():out.append(dict(id=p.parent.name,map_id=d['map_id'],deleted_at=d['deleted_at']))
        except (OSError,ValueError,KeyError):pass
    return sorted(out,key=lambda x:x['deleted_at'],reverse=True)

def delete(c,ident,expected):
    c.assert_no_motion();d=c.state()
    if d.get('phase') in ('mapping','starting','validating_map','recovering'):raise ValueError('请先完成当前扫图或定位操作，再删除地图')
    src=map_path(c,ident)
    if not expected or expected!=version(c,ident):raise ValueError('地图内容已变化，请刷新后重新确认删除')
    selection=c.MPPI/'selection.json';selected=c.read(selection) if selection.exists() else None
    active=d.get('map_id')==ident or (selected or {}).get('map_id')==ident
    # Archive named goals before removing their owning map. Stop only Nav2.
    if active:c.archive_state();c.run(['bash','MPPI导航.sh','stop'])
    token=str(time.time_ns())+'-'+uuid.uuid4().hex[:8];dest=c.MPPI/'maps-trash'/token;dest.mkdir(parents=True)
    c.write(dest/'receipt.json',dict(map_id=ident,deleted_at=time.time(),state=d if d.get('map_id')==ident else None))
    src.rename(dest/'map')
    try:
        if active:
            if selected and selected.get('map_id')==ident:selection.unlink()
            c.save(phase='idle',map_id=None,session=None,points={},selected=None,preview=None,route=None,route_preview=None,recovery_error=None)
    except BaseException:
        (dest/'map').rename(src)
        if active:
            if selected is not None:c.write(selection,selected)
            c.write(c.STATE,d)
        raise
    print('地图已移入回收站：'+ident+'；可从网页恢复。融合未重启。',flush=True)
    return token

def restore(c,token):
    c.assert_no_motion()
    if c.state().get('phase') in ('mapping','starting','validating_map','recovering'):raise ValueError('请先完成当前扫图或定位操作')
    src=c.MPPI/'maps-trash'/safe_id(token)
    if src.is_symlink() or (src/'map').is_symlink():raise ValueError('不支持回收站链接')
    receipt=c.read(src/'receipt.json');ident=safe_id(receipt['map_id']);dest=c.MPPI/'maps'/ident
    if dest.exists() or dest.is_symlink():raise ValueError('同名地图已存在，未覆盖任何地图')
    if not (src/'map').is_dir():raise ValueError('回收站地图已恢复或不存在')
    (src/'map').rename(dest)
    print('地图已恢复：'+ident+'；请选择并加载，重新定位后再导航。',flush=True)
