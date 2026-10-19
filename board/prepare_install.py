#!/usr/bin/env python3
"""Bind an application release to the validated native fusion and device calibration."""
import argparse
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--fusion-release',type=Path,required=True)
p.add_argument('--sensor-base',type=Path,default=Path('/home/unitree/fast_livo2_port/build1'));a=p.parse_args()
for f in (a.fusion_release/'ws/devel/lib/fast_livo/fastlivo_mapping',a.sensor_base/'mapping/jpeg_build/livo_jpeg'):
    if not f.is_file():raise SystemExit('Required native executable missing: '+str(f))
if (root/'current.json').exists():raise SystemExit('Already used release; do not rebind a live deployment')
cal=root/'calibration';cal.mkdir(exist_ok=True)
for name in ('livo.yaml','camera.yaml'):shutil.copy2(a.fusion_release/name,cal/name)
cfg=dict(backend='board',fusion_release=str(a.fusion_release),sensor_base=str(a.sensor_base),
         profile='MAXN-4threads-LIVO5Hz-filter4-surf0.15',image_hz=5,omp_threads=4,
         cuda_backend='cpu',nav_image='go2w-nav2-mppi:humble',
         machine_id=Path('/etc/machine-id').read_text().strip(),autostart_motion=False)
(root/'deployment.json').write_text(json.dumps(cfg,indent=2))
print(json.dumps(cfg,indent=2))
