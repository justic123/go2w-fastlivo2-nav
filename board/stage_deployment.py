#!/usr/bin/env python3
"""Package board application and saved maps, excluding recordings and credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--code-only',action='store_true',help='Update application without overwriting robot maps or speed selection');a=p.parse_args()
files=set()
for directory in ('board','demo','lifecycle','navigation/mppi','navigation/nav2','visualization'):
    for f in (root/directory).rglob('*'):
        if not f.is_file() or f.is_symlink():continue
        rel=f.relative_to(root)
        if any(x in rel.parts for x in ('runs','evidence','client','backups','build','__pycache__','maps','maps-trash','web-state','calibration')):continue
        if any(x.startswith('map-save-') for x in rel.parts):continue
        if f.suffix not in ('.py','.sh','.md','.yaml','.xml','.rviz','.cpp','.cu','.h','.json','.gpg','.html','.css','.js','.patch') and f.name not in ('Dockerfile','CMakeLists.txt'):continue
        if f.name in ('source-manifest.json','current.json','selection.json','state.json','deployment.json','demo_nav.yaml','speed_profile.json'):continue
        files.add(rel)
for name in ('monitor.py','ros1_view_source.py','backlog_policy.py'):
    files.add(Path('desktop')/name)
for name in ('select_speed.py','test_select_speed.py'):
    files.add(Path('migration')/name)
for name in ('MPPI导航.sh','板载运行.sh','板载可视化.sh','网页控制台.sh','交互演示控制台使用说明.md','THIRD_PARTY_NOTICES.md','LICENSE'):
    if (root/name).is_file():files.add(Path(name))
for f in (() if a.code_only else (root/'navigation/mppi/maps').glob('*/*')):
    if f.is_file() and f.name in ('points.npy','map.pgm','map.yaml','metadata.json','console_points.json','localization_anchors.json','source_costmap.npy','display-rgb.bin','display-rgb.json'):
        files.add(f.relative_to(root))
profile=root/'navigation/mppi/speed_profile.json'
if not a.code_only and profile.is_file():files.add(profile.relative_to(root))
manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
              includes_working_changes=True,sha256={str(n):hashlib.sha256((root/n).read_bytes()).hexdigest() for n in sorted(files)})
manifest_path=a.output.with_suffix('.manifest.json');manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
with tarfile.open(a.output,'w:gz') as tar:
    for rel in sorted(files):tar.add(root/rel,arcname=str(rel),recursive=False)
    tar.add(manifest_path,arcname='board/source-manifest.json')
print(json.dumps(dict(archive=str(a.output),files=len(files),bytes=a.output.stat().st_size)))
