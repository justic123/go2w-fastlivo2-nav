#!/usr/bin/env bash
# 一次性修复部署：仅在采集已正常停止时更新，不自动清地图或重启机器狗。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
sock="$HOME/.ssh/go2w-mapping.sock"
ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1 || { echo '先用 重新采集.sh start 建立连接，再按文档stop保存后更新。';exit 1; }
state=$(ssh -S "$sock" unitree@192.168.123.18 python3 /home/unitree/fast_livo2_port/build1/capture_control.py status)
/usr/bin/python3 - "$state" <<'PY'
import sys,json
if json.loads(sys.argv[1]).get('running'):raise SystemExit('采集正在运行。先执行 导航预演.sh stop 和 重新采集.sh stop，等待保存完成。')
PY
scp -o ControlPath="$sock" "$folder/visualization/ros1_view_source.py" unitree@192.168.123.18:/home/unitree/fast_livo2_port/build1/mapping/ros1_view_source.py.next
ssh -S "$sock" unitree@192.168.123.18 'python3 - <<'"'"'PY'"'"'
import py_compile,shutil,time,json,subprocess
from pathlib import Path
root=Path("/home/unitree/fast_livo2_port/build1")
s=json.loads(subprocess.check_output(["python3",str(root/"capture_control.py"),"status"]))
if s.get("running"):raise SystemExit("Capture started while staging; update refused")
p=root/"mapping/ros1_view_source.py";tmp=p.with_name(p.name+".next")
py_compile.compile(str(tmp),doraise=True)
backup=p.with_name(p.name+".before-session-fix-"+str(time.time_ns()))
shutil.copy2(p,backup);tmp.replace(p)
print("显示程序已更新，旧版本保留："+str(backup))
print("现在可start开始新一轮建图，并使用新版笔记本显示接收程序。")
PY'
