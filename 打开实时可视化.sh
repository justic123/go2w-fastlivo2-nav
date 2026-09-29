#!/usr/bin/env bash
# 笔记本显示入口。关闭本窗口仅结束本入口启动的显示进程，不停止板端SLAM。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ "${1:-}" != --clean ]]; then
 exec env -i HOME="$HOME" USER="${USER:-river}" PATH=/usr/bin:/bin LANG=C.UTF-8 DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" QT_SCALE_FACTOR=1 QT_AUTO_SCREEN_SCALE_FACTOR=0 QT_ENABLE_HIGHDPI_SCALING=0 bash "$0" --clean
fi
sock="${HOME}/.ssh/go2w-mapping.sock"
ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1 || { echo '请先运行 重新采集.sh start';exit 1; }
# 转发是显示链路；已存在的转发无需重复建立。
for port in 11325 11327; do
 if ! python3 - "$port" <<'PY'
import socket,sys
# 检测监听，不消耗板端单客户端连接。
port=int(sys.argv[1]);s=socket.socket()
try:s.bind(('127.0.0.1',port))
except OSError:raise SystemExit(0)
else:s.close();raise SystemExit(1)
PY
 then ssh -S "$sock" -O forward -L "127.0.0.1:$port:127.0.0.1:$port" unitree@192.168.123.18; fi
done
set +u
source /opt/ros/humble/setup.bash
set -u
export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1
children=()
cleanup(){ for p in "${children[@]}";do kill -TERM "$p" 2>/dev/null || true;done; }
trap cleanup EXIT
trap 'exit 0' INT TERM
if ! pgrep -f '[p]ython3 .*visualization/ros2_view.py' >/dev/null;then python3 "$folder/visualization/ros2_view.py" & children+=($!);fi
if ! pgrep -f '[p]ython3 .*nav2/local_view.py' >/dev/null;then python3 "$folder/navigation/nav2/local_view.py" & children+=($!);fi
# Reuse this user's matching RViz window; repeated start must not open duplicate viewers.
existing_rviz=$(python3 - "$folder/visualization/go2w_live_map.rviz" <<'PYVIEW'
from pathlib import Path
import os,sys
wanted=Path(sys.argv[1]).resolve()
for d in Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  if d.stat().st_uid!=os.getuid():continue
  args=(d/'cmdline').read_bytes().split(b'\0');args=[x.decode() for x in args if x]
  if not args or Path(args[0]).name!='rviz2' or '-d' not in args:continue
  config=Path(args[args.index('-d')+1])
  if not config.is_absolute():config=(d/'cwd').resolve()/config
  if config.resolve()==wanted:print(d.name);break
 except (OSError,ValueError,IndexError):pass
PYVIEW
)
if [[ -n "$existing_rviz" ]];then
 echo '复用已打开的RViz窗口。'
 while kill -0 "$existing_rviz" 2>/dev/null;do sleep 1;done
else
 rviz2 -d "$folder/visualization/go2w_live_map.rviz" & children+=($!)
 wait "${children[-1]}"
fi
