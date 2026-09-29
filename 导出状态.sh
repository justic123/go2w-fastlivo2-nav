#!/usr/bin/env bash
# 查看本版停止后在后台排队/执行的地图导出，不启动或停止任何服务。
set -euo pipefail
timeout --foreground 12s ssh -S "$HOME/.ssh/go2w-mapping.sock" -o BatchMode=yes -o ConnectTimeout=5 unitree@192.168.123.18 python3 - <<'PY'
import sys,json
from pathlib import Path
sys.path.insert(0,'/home/unitree/fast_livo2_port/build1/lifecycle')
from service_core import ROOT,read,alive
pending=[];failed=[];completed=0
for p in ROOT.glob('*/export_status.json'):
 s=read(p);phase=s.get('phase')
 if phase=='complete':completed+=1
 elif phase in ('queued','running','paused_for_mapping'):
  if not alive(s):s.update(phase='interrupted',note='后台导出进程已退出，原始bag保留');failed.append(s)
  else:pending.append(s)
 elif phase=='failed':failed.append(s)
print(json.dumps(dict(pending=pending,failed=failed,completed=completed,all_exports_complete=not pending and not failed),ensure_ascii=False,indent=2))
PY
