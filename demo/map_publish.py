"""Publish a complete map directory by rename; leave prior maps untouched on failure."""
import json,shutil,tempfile
from pathlib import Path

def publish(source,points,dest,session,rgb_cache=None):
    source,points,dest=map(Path,(source,points,dest))
    if json.loads((source/'metadata.json').read_text()).get('session')!=session:raise ValueError('地图会话不一致')
    if dest.exists() or dest.is_symlink():raise ValueError('同名地图已存在，不覆盖')
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Outside maps/: readers must never see a half-copied map as loadable.
    stage=Path(tempfile.mkdtemp(prefix='map-save-',dir=dest.parent.parent))
    try:
        for n in ('map.yaml','map.pgm','metadata.json'):
            if not (source/n).is_file():raise ValueError('地图文件缺失：'+n)
            shutil.copy2(source/n,stage/n)
        if (source/'source_costmap.npy').is_file():shutil.copy2(source/'source_costmap.npy',stage/'source_costmap.npy')
        shutil.copy2(points,stage/'points.npy')
        if rgb_cache is not None:
            try:
                cache=Path(rgb_cache);meta=json.loads((cache/'native-rgb.json').read_text())
                # Only a mapping-session capture shares this frozen map frame.
                if meta.get('session')==session and meta.get('from_mapping') and meta.get('frame')=='camera_init':
                    data=(cache/'native-rgb.bin').read_bytes()
                    if json.loads((cache/'native-rgb.json').read_text())==meta and len(data)==meta['count']*24 and 0<meta['count']<=400000:
                        (stage/'display-rgb.bin').write_bytes(data)
                        (stage/'display-rgb.json').write_text(json.dumps(dict(meta,map_id=dest.name,frame='map')))
            except (OSError,ValueError,KeyError):pass  # Display absence must not discard a valid navigation map.
        stage.rename(dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
