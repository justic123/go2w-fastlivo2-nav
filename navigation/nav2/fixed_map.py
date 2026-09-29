"""Same-session fixed navigation baseline. This does not freeze FAST-LIVO2."""
import json
from pathlib import Path
import yaml
from mapping_session import current_mapping_run

def configure(root, source, output):
    root=Path(root); selection=root/'fixed_navigation_map.json'
    config=yaml.safe_load(Path(source).read_text())
    if selection.exists():
        selected=json.loads(selection.read_text())
        if selected['mapping_run'] != current_mapping_run(root):
            raise RuntimeError('Fixed map belongs to another SLAM session; rebuild/select live mode')
        mapfile=Path(selected['yaml'])
        if not mapfile.is_file():raise RuntimeError('Fixed map file missing')
        config['map_server']={'ros__parameters':{'use_sim_time':False,'yaml_filename':str(mapfile),'topic_name':'/map','frame_id':'camera_init'}}
        params=config['global_costmap']['global_costmap']['ros__parameters']
        params['plugins']=['static_layer','obstacle_layer','inflation_layer']
        params['static_layer']={'plugin':'nav2_costmap_2d::StaticLayer','map_topic':'/map','map_subscribe_transient_local':True,'subscribe_to_updates':False}
        config['lifecycle_manager']['ros__parameters']['node_names']=['map_server','planner_server','controller_server']
    Path(output).write_text(yaml.safe_dump(config,sort_keys=False))
    return selection.exists()
