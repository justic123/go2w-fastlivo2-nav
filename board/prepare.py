#!/usr/bin/env python3
"""Stage a board experiment from the pinned, restored upstream tree. No live edits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=HERE.parent / 'upstream/FAST-LIVO2')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit('Output must not exist; preserve previous experiments')
dependency = next(x for x in json.loads((HERE.parent/'dependencies/sources.json').read_text())
                  if x['path'] == 'upstream/FAST-LIVO2')
head = subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
if head != dependency['commit']:
    raise SystemExit('Unexpected upstream revision')
working_patch = subprocess.check_output(['git', '-C', str(args.source), 'diff', '--binary', 'HEAD'])
if hashlib.sha256(working_patch).hexdigest() != dependency['patch_sha256']:
    raise SystemExit('Restored dependency has unexpected local changes; preserve and inspect them')
shutil.copytree(args.source, args.output, ignore=shutil.ignore_patterns('.git', 'Log', 'build', '__pycache__'))
subprocess.run(['git', 'apply', '--check', str(HERE/'fast_livo2.patch')], cwd=args.output, check=True)
subprocess.run(['git', 'apply', str(HERE/'fast_livo2.patch')], cwd=args.output, check=True)
subprocess.run(['git', 'apply', '--check', str(HERE/'visual_index.patch')], cwd=args.output, check=True)
subprocess.run(['git', 'apply', str(HERE/'visual_index.patch')], cwd=args.output, check=True)
for source, target in [('support/board_profile.h', 'include/board_profile.h'),
                       ('support/voxel_index.h', 'include/voxel_index.h'),
                       ('support/board_profile.cpp', 'src/board_profile.cpp'),
                       ('cuda/normal_equations.h', 'include/normal_equations.h'),
                       ('cuda/normal_equations.cu', 'src/normal_equations.cu')]:
    shutil.copy2(HERE/source, args.output/target)
manifest = {str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in args.output.rglob('*') if p.is_file()}
(args.output/'board-source-manifest.json').write_text(json.dumps(dict(upstream=head, files=manifest), indent=2))
(args.output/'Log').mkdir()
print(args.output)
