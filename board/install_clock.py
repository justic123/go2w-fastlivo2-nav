#!/usr/bin/env python3
"""Correct the board RTC and its late boot restore, only while fusion is stopped."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--epoch',type=int,required=True);a=p.parse_args()
    if os.geteuid()!=0:raise SystemExit('Run with sudo on the board')
    if not 1704067200<=a.epoch<=4102444800:raise SystemExit('Invalid UTC epoch')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            cmd=(proc/'cmdline').read_bytes().split(b'\0')
            if cmd and (Path(cmd[0].decode()).name in ('fastlivo_mapping','xt16_driver') or
                        any(b'guard_server.py' in w or b'/relay.py' in w for w in cmd)):
                raise SystemExit('Stop fusion and motion before adjusting system time')
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    rtc=Path('/sys/class/rtc/rtc0')
    if not rtc.exists() or 'nvvrs' not in (rtc/'name').read_text():
        raise SystemExit('Expected board RTC0 not found; refusing to select an RTC blindly')
    rc=Path('/etc/rc.local');original=rc.read_text()
    desired='/sbin/hwclock --hctosys --utc --rtc=/dev/rtc0'
    updated,count=re.subn(r'(?m)^[ \t]*`?hwclock\s+-s`?[ \t]*$',desired,original)
    if count!=1 and desired not in original:raise SystemExit('Unexpected rc.local clock command; inspect before changing it')
    backup=Path('/var/lib/go2w-deployment/clock');backup.mkdir(parents=True,exist_ok=True)
    saved=backup/('rc.local-'+hashlib.sha256(original.encode()).hexdigest()[:16])
    if updated!=original:
        if not saved.exists():shutil.copy2(rc,saved)
        temp=rc.with_suffix('.go2w-tmp');shutil.copy2(rc,temp);temp.write_text(updated);temp.replace(rc)
    subprocess.run(['/bin/date','-u','-s','@'+str(a.epoch)],check=True)
    subprocess.run(['/sbin/hwclock','--systohc','--utc','--rtc=/dev/rtc0'],check=True)
    # RTC1 is the Tegra counter. Keep it coherent now; boot explicitly restores RTC0.
    other=subprocess.run(['/sbin/hwclock','--systohc','--utc','--rtc=/dev/rtc1'],capture_output=True,text=True)
    clock=Path('/var/lib/systemd/timesync/clock');clock.touch();os.utime(clock,None)
    result=dict(epoch=time.time(),rtc0_name=(rtc/'name').read_text().strip(),
                rtc0_date=(rtc/'date').read_text().strip(),rtc0_time=(rtc/'time').read_text().strip(),
                rtc1_write_code=other.returncode,late_boot_restore=desired,backup=str(saved),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    (backup/'installed.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
