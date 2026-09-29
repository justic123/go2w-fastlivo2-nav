#!/usr/bin/env bash
# 默认只预演，不发运控指令。execute 必须由使用者显式选择。
set -euo pipefail
action=${1:-preview}
distance=${2:-0.5}
case "$action" in preview|execute) ;; *) echo '用法: 点到点测试.sh [preview|execute] [距离米，0.1–0.5]'; exit 2;; esac
[[ "$distance" =~ ^0\.[0-9]+$ ]] || { echo '距离须写为小数，例如0.5'; exit 2; }
/usr/bin/python3 - "$distance" <<'PY'
import sys
if not .1<=float(sys.argv[1])<=.5:raise SystemExit('距离范围0.1–0.5米')
PY
sock="${HOME}/.ssh/go2w-mapping.sock"
if ! ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1; then
  # 密码由终端交互输入，不写进脚本；保持主机密钥验证。
  ssh -M -S "$sock" -o ControlPersist=12h -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -fN unitree@192.168.123.18
fi
run="point-${action}-$(date +%Y%m%d-%H%M%S)-$RANDOM"
if [[ "$action" == execute ]]; then
  echo '即将执行真实运动：请停止遥控扫图，只保留紧急接管；5秒内可按Ctrl+C取消启动。'
  for countdown in 5 4 3 2 1; do echo "启动倒计时 $countdown"; sleep 1; done
fi
flag=
[[ "$action" != execute ]] || flag=--execute
echo "模式=$action 距离=${distance}m 结果=/home/unitree/fast_livo2_port/build1/$run"
# 变量仅来自上面的枚举、数字校验和系统生成名称。
ssh -S "$sock" -o ConnectTimeout=5 unitree@192.168.123.18 "bash -s -- '$run' '$distance' '$flag'" <<'REMOTE'
set -eo pipefail
source /opt/ros/noetic/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1 ROS_HOSTNAME=localhost OPENBLAS_NUM_THREADS=1
root=/home/unitree/fast_livo2_port/build1
# 即使第二个使用者误点击，也不允许并发下发运动指令。
exec 8>"$root/point_trial.lock"
flock -n 8 || { echo '已有点到点测试运行'; exit 1; }
args=(--output "$root/$1" --distance "$2" --point-test)
[[ -z "$3" ]] || args+=(--execute)
python3 "$root/navigation/point_trial.py" "${args[@]}"
REMOTE
