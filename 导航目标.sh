#!/usr/bin/env bash
# preview：完整控制链不发运控；execute：真实运动；stop：终止当前目标。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
action=${1:-status};sock="$HOME/.ssh/go2w-mapping.sock"
ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1 || { echo '请先执行 ./一键启动.sh start';exit 1; }
case "$action" in
 status|stop) timeout --foreground 12s ssh -o ConnectTimeout=5 -S "$sock" unitree@192.168.123.18 python3 /home/unitree/fast_livo2_port/build1/navigation/nav2/goal_control.py "$action";;
 preview|execute) exec /usr/bin/python3 "$folder/navigation/nav2/laptop_goal.py" "$action" "${2:-0.5}" "${3:-0.0}";;
 *) echo '用法: 导航目标.sh [status|stop|preview|execute] [前方米] [左方米]';exit 2;;
esac
