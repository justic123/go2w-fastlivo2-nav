#!/usr/bin/env bash
# 电脑只负责显示；DDS不暴露到机器人控制网络。关闭本窗口不停止板载定位。
set -euo pipefail
cd -- "$(dirname -- "$0")"
mode=${1:-navigation}
[[ "$mode" =~ ^(navigation|cloud|mapping)$ ]] || { echo '用法: bash 板载可视化.sh navigation|cloud|mapping'; exit 2; }
[[ ! -f board/deployment.json ]] || { echo '请在 Ubuntu 22.04 电脑上运行此显示入口'; exit 1; }
sock="${GO2W_BOARD_SSH_SOCKET:-/tmp/go2w-board-view-$UID.sock}"
if ! ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1; then
 ssh -M -S "$sock" -o ControlPersist=12h -o ConnectTimeout=6 -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -fN \
   -L 127.0.0.1:11345:127.0.0.1:11345 -L 127.0.0.1:11335:127.0.0.1:11335 unitree@192.168.123.18
fi
frame=$(ssh -S "$sock" -o BatchMode=yes unitree@192.168.123.18 'python3 -c '\''import json; from pathlib import Path; r=Path("/home/unitree/fast_livo2_port/onboard/current"); p=r/"demo/state.json"; d=json.loads(p.read_text()) if p.exists() else {}; print("map" if (r/"navigation/mppi/selection.json").exists() or d.get("map_id") else "camera_init")'\''')
exec env -i HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin LANG=C.UTF-8 DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
 /bin/bash board/view_inside.sh "$PWD" "$mode" "$frame"
