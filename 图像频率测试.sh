#!/usr/bin/env bash
# 5Hz测试只改图像抽帧，不改变分辨率、标定、运控；不会自动行走。
set -euo pipefail
cd -- "$(dirname -- "$0")"
sock="$HOME/.ssh/go2w-mapping.sock";root=/home/unitree/fast_livo2_port/build1
remote(){ timeout --foreground 15s ssh -S "$sock" -o ConnectTimeout=5 unitree@192.168.123.18 python3 "$root/lifecycle/image_profile.py" "$1"; }
case "${1:-start}" in
 start|rollback)
  if ! ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1;then
   mkdir -p "$HOME/.ssh"
   ssh -M -S "$sock" -o ControlPersist=12h -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -fN unitree@192.168.123.18
  fi
  mode=5hz;[[ "${1:-start}" != rollback ]] || mode=baseline
  state=$(remote status)
  if ! /usr/bin/python3 -c 'import json,sys;s=json.loads(sys.argv[1]);sys.exit(0 if s["configured"]==sys.argv[2] and (not s["running"] or s["active"]==sys.argv[2]) else 1)' "$state" "$mode";then
   echo '切换图像频率：保存并停止旧轮，开始新地图。请保持静止。'
   bash ./楼层建图.sh stop
   remote "$mode"
  fi
  exec bash ./楼层建图.sh start;;
 status) remote status;exec bash ./楼层建图.sh status;;
 stop) exec bash ./楼层建图.sh stop;;
 check)
  timeout --foreground 30s ssh -S "$sock" -o ConnectTimeout=5 unitree@192.168.123.18 'bash -c "source /opt/ros/noetic/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1; exec python3 /home/unitree/fast_livo2_port/build1/lifecycle/measure_image_rate.py"';;
 *) echo '用法: 图像频率测试.sh start/status/check/stop/rollback';exit 2;;
esac
