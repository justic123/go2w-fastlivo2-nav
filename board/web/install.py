#!/usr/bin/env python3
import os,subprocess
from pathlib import Path
from common import ROOT
if os.geteuid()!=0 or not (ROOT/'board/deployment.json').exists():raise SystemExit('Run as root on deployed Go2W')
unit='''[Unit]
Description=Go2W onboard web dashboard (no automatic robot motion)
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory={root}
Environment=HOME=/home/unitree PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 {root}/board/web/service.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=40
KillMode=mixed
UMask=0077

[Install]
WantedBy=multi-user.target
'''.format(root=ROOT)
Path('/etc/systemd/system/go2w-web.service').write_text(unit)
subprocess.run(['systemctl','daemon-reload'],check=True)
# Autostart is limited to the web page and passive displays, never mapping or motion.
subprocess.run(['systemctl','enable','--now','go2w-web.service'],check=True)
print('网页服务已安装并开机启动；不会自动启动建图、导航或运动。')
