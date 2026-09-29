#!/usr/bin/env bash
# 本机算法实验，不接入导航或运控。切换计算位置会开始新地图。
set -euo pipefail
cd -- "$(dirname -- "$0")";folder=$PWD;sock="$HOME/.ssh/go2w-mapping.sock";board=/home/unitree/fast_livo2_port/build1
remote(){ timeout --foreground 12s ssh -S "$sock" -o ConnectTimeout=5 unitree@192.168.123.18 python3 "$board/lifecycle/compute_profile.py" "$1"; }
case "${1:-start}" in
 start)
  docker image inspect go2w-livo-desktop:20260928 >/dev/null
  if ! ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1;then
   mkdir -p "$HOME/.ssh"
   ssh -M -S "$sock" -o ControlPersist=12h -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -fN unitree@192.168.123.18
  fi
  current=$(remote status)
  if [[ "$current" != desktop ]];then
   bash ./楼层建图.sh stop
   remote desktop
   ssh -S "$sock" unitree@192.168.123.18 python3 "$board/lifecycle/image_profile.py" 10hz
  fi
  # SSH tunnel carries raw sensor data; tolerate a previously established forward.
  if /usr/bin/python3 - <<'PY'
import socket
s=socket.socket()
try:s.bind(('127.0.0.1',11329))
except OSError:raise SystemExit(1)
PY
  then ssh -S "$sock" -O forward -L 127.0.0.1:11329:127.0.0.1:11329 unitree@192.168.123.18;fi
  bash ./重新采集.sh start
  /usr/bin/python3 ./desktop/control.py start
  echo '正在等待本机真实处理延迟达标，请保持静止。'
  for i in {1..60};do
   state=$(/usr/bin/python3 ./desktop/control.py status)
   if /usr/bin/python3 -c 'import json,sys;sys.exit(0 if json.loads(sys.argv[1]).get("ready") else 1)' "$state";then
    bash ./desktop/open_view.sh
    echo '本机建图已就绪；导航运控关闭。';exit 0
   fi
   sleep 1
  done
  echo "$state";echo '本机未就绪，请查看desktop/runs内日志。';exit 1;;
 status) exec /usr/bin/python3 ./desktop/control.py status;;
 check) exec docker exec go2w-livo-desktop bash -c 'source /work/ws/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11331 ROS_IP=127.0.0.1; exec python3 /work/measure_image_rate.py';;
 stop)
  bash ./本机导航测试.sh stop
  /usr/bin/python3 ./desktop/control.py stop
  bash ./重新采集.sh stop
  bash ./关闭本机显示接收.sh;;
 board)
  bash ./本机建图测试.sh stop
  remote board
  ssh -S "$sock" unitree@192.168.123.18 python3 "$board/lifecycle/image_profile.py" 5hz
  echo '已恢复板端模式，当前未启动；保持静止后运行 图像频率测试.sh start。';;
 *) echo '用法: 本机建图测试.sh start/status/check/stop/board';exit 2;;
esac
