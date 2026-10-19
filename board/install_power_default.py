#!/usr/bin/env python3
"""Set the vendor MAXN profile as the boot default; preserve thermal controls."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo on the Go2W Orin NX')
    cfg = Path('/etc/nvpmodel.conf')
    original = cfg.read_text()
    if not re.search(r'< POWER_MODEL ID=0 NAME=MAXN >', original):
        raise SystemExit('Vendor MAXN profile 0 missing; refusing to guess')
    updated, count = re.subn(r'< PM_CONFIG DEFAULT=\d+ >', '< PM_CONFIG DEFAULT=0 >', original)
    if count != 1:
        raise SystemExit('Expected exactly one PM_CONFIG default')
    backup = Path('/var/lib/go2w-deployment/power')
    backup.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(original.encode()).hexdigest()
    if updated != original:
        saved = backup / ('nvpmodel-' + digest[:16] + '.conf')
        if not saved.exists():
            shutil.copy2(cfg, saved)
        temp = cfg.with_suffix('.go2w-tmp')
        shutil.copy2(cfg, temp)
        temp.write_text(updated)
        temp.replace(cfg)
    subprocess.run(['systemctl', 'enable', 'nvpmodel.service'], check=True)
    subprocess.run(['/usr/sbin/nvpmodel', '-m', '0'], check=True)
    mode = subprocess.check_output(['/usr/sbin/nvpmodel', '-q'], text=True)
    if 'NV Power Mode: MAXN' not in mode or Path('/var/lib/nvpmodel/status').read_text().strip() != 'pmode:0000':
        raise SystemExit('MAXN did not apply; inspect vendor nvpmodel output')
    result = dict(default_mode=0, mode=mode.strip(), backup_directory=str(backup),
                  cpu_online=Path('/sys/devices/system/cpu/online').read_text().strip(),
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  config_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),
                  jetson_clocks_modified=False, thermal_controls_modified=False)
    (backup / 'installed.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
