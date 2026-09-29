#!/usr/bin/env python3
"""Restore pinned dependency sources into missing directories; never overwrite an existing tree."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for item in json.loads((HERE / 'sources.json').read_text()):
    dest = ROOT / item['path']
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        print('SKIP existing:', dest)
        continue
    patch = HERE / item['patch']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != item['patch_sha256']:
        raise SystemExit('Patch checksum mismatch: ' + str(patch))
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--no-checkout', item['url'], str(dest)], check=True)
    subprocess.run(['git', '-C', str(dest), 'checkout', '--detach', item['commit']], check=True)
    if patch.stat().st_size:
        subprocess.run(['git', '-C', str(dest), 'apply', '--binary', str(patch)], check=True)
    for name in item['extras']:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / 'extras' / item['path'].replace('/', '__') / name, target)
    print('RESTORED:', item['path'], item['commit'])
