#!/usr/bin/env bash
# 全部模式都不发送机器人运控指令；plan会采样隔离的建议速度。
set -euo pipefail
action=${1:-status};distance=${2:-0.8};sock="${HOME}/.ssh/go2w-mapping.sock"
case "$action" in start|stop|status|plan) ;; *) echo '用法: 导航预演.sh [start|stop|status|plan] [前方距离米，最大5]';exit 2;; esac
[[ "$distance" =~ ^[0-9]+(\.[0-9]+)?$ ]] || exit 2
/usr/bin/python3 - "$distance" <<'PY'
import sys
if not 0<float(sys.argv[1])<=5:raise SystemExit('规划预演距离0–5米，不会运动')
PY
ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1 || { echo '请先运行 重新采集.sh start 建立连接';exit 1; }
root=/home/unitree/fast_livo2_port/build1
if [[ "$action" == plan ]]; then
 run="nav-plan-$(date +%Y%m%d-%H%M%S)-$RANDOM.json"
 echo "仅规划，不运动。结果保存到 $root/$run"
 ssh -S "$sock" unitree@192.168.123.18 "bash -s -- '$distance' '$run'" <<'REMOTE'
set -e
source /opt/ros/foxy/setup.bash
export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1
python3 /home/unitree/fast_livo2_port/build1/navigation/nav2/plan_probe.py --forward "$1" --sample-controller --output "/home/unitree/fast_livo2_port/build1/$2"
REMOTE
else
 timeout --foreground 45s ssh -S "$sock" -o ConnectTimeout=5 unitree@192.168.123.18 python3 "$root/navigation/nav2/control.py" "$action" "nav2-preview-$(date +%Y%m%d-%H%M%S)-$RANDOM"
fi
