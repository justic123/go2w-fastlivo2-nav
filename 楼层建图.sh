#!/usr/bin/env bash
# 楼层服务入口。start不运动、不自动发目标；已有楼层采集则复用。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd);cd "$folder"
sock="$HOME/.ssh/go2w-mapping.sock";root=/home/unitree/fast_livo2_port/build1
action=${1:-start}
connect(){
 mkdir -p "$HOME/.ssh";chmod 700 "$HOME/.ssh"
 if ! ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1;then
  ssh -M -S "$sock" -o ControlPersist=12h -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -fN unitree@192.168.123.18
 fi
}
case "$action" in
 start|rollback)
  connect;mode=floor;[[ "$action" != rollback ]] || mode=short
  current=$(timeout --foreground 12s ssh -o ConnectTimeout=5 -S "$sock" unitree@192.168.123.18 python3 "$root/navigation/nav2/nav_profile.py" status)
  if [[ "$current" != "$mode" ]];then
   echo '切换模式会先保存并结束旧建图；新会话的地点坐标需重新记录。'
   bash ./一键启动.sh stop
   timeout --foreground 12s ssh -o ConnectTimeout=5 -S "$sock" unitree@192.168.123.18 python3 "$root/navigation/nav2/nav_profile.py" "$mode"
  fi
  exec bash ./一键启动.sh start;;
 status) connect;timeout --foreground 12s ssh -o ConnectTimeout=5 -S "$sock" unitree@192.168.123.18 python3 "$root/navigation/nav2/nav_profile.py" status;exec bash ./一键启动.sh status;;
 save)
  connect
  ssh -S "$sock" unitree@192.168.123.18 'bash -c "source /opt/ros/foxy/setup.bash; export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1; exec python3 /home/unitree/fast_livo2_port/build1/navigation/nav2/save_floor_map.py"';;
 stop)
  connect
  bash ./导航目标.sh stop
  # Save observed navigation space before stopping costmap publishers.
  nav_state=$(bash ./导航预演.sh status) || nav_state='{}'
  if /usr/bin/python3 -c 'import json,sys;sys.exit(0 if json.loads(sys.argv[1]).get("ready") else 1)' "$nav_state";then
   echo '正在保存导航地图快照（最多18秒），随后停止服务。'
   if ! timeout --foreground 18s bash ./楼层建图.sh save;then echo '代价图快照未保存；继续停止采集，原始录包保留。';fi
  else echo '导航未就绪，跳过快照并继续停止。';fi
  exec bash ./一键启动.sh stop;;
 *) echo '用法: 楼层建图.sh start/status/save/stop/rollback';exit 2;;
esac
