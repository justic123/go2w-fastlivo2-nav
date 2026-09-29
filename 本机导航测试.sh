#!/usr/bin/env bash
# 本机FAST-LIVO2定位回传板端Nav2；start仅规划服务，不执行运动。
set -euo pipefail
cd -- "$(dirname -- "$0")"
sock="$HOME/.ssh/go2w-mapping.sock";board=/home/unitree/fast_livo2_port/build1
action=${1:-status}
case "$action" in
 start)
 /usr/bin/python3 desktop/control.py status > desktop/nav_preflight.json
 session=$(/usr/bin/python3 - <<'PY'
import json
s=json.load(open('desktop/nav_preflight.json'))
if not s.get('ready'):raise SystemExit('本机建图未就绪')
print(s['run'])
PY
 )
 if ! docker exec go2w-livo-desktop bash -c 'pgrep -f "^python3 /work/nav_return.py " >/dev/null';then
 docker exec -d go2w-livo-desktop bash -c 'source /work/ws/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11331 ROS_IP=127.0.0.1; exec python3 /work/nav_return.py "/work/runs/$1" > "/work/runs/$1/nav_return.log" 2>&1' _ "$session"
 fi
 # The reverse forward is loopback-only on the robot.
 ssh -S "$sock" -O forward -R 127.0.0.1:11337:127.0.0.1:11337 unitree@192.168.123.18 2>/dev/null || true
 /usr/bin/python3 -c 'import json,sys;print(json.dumps(dict(session=sys.argv[1])))' "$session" | ssh -S "$sock" unitree@192.168.123.18 'python3 -c '\''import json,sys,pathlib;d=json.load(sys.stdin);p=pathlib.Path("/home/unitree/fast_livo2_port/build1/desktop_navigation.json");p.write_text(json.dumps(d))'\'''
 ssh -S "$sock" unitree@192.168.123.18 python3 "$board/navigation/nav2/control.py" start "desktop-nav-$(date +%Y%m%d-%H%M%S)-$$"
 ssh -S "$sock" -O forward -L 127.0.0.1:11327:127.0.0.1:11327 unitree@192.168.123.18 2>/dev/null || true
 if ! pgrep -f '[p]ython3 .*nav2/local_view.py' >/dev/null;then
  setsid -f env -i HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1; exec python3 "$1/navigation/nav2/local_view.py"' _ "$PWD" > desktop/logs/nav_view.log 2>&1 < /dev/null
 fi
 ;;
 freeze)
 bash ./导航目标.sh stop
 # Wait for the owned goal to finish before changing planning services.
 for i in {1..25};do
  state=$(bash ./导航目标.sh status)
  if /usr/bin/python3 -c 'import json,sys;sys.exit(bool(json.loads(sys.argv[1]).get("running")))' "$state";then break;fi
  sleep .2
 done
 /usr/bin/python3 -c 'import json,sys;sys.exit(bool(json.loads(sys.argv[1]).get("running")))' "$state"
 ssh -S "$sock" unitree@192.168.123.18 "env -i HOME=/home/unitree PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c 'source /opt/ros/foxy/setup.bash; export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1; exec python3 /home/unitree/fast_livo2_port/build1/navigation/nav2/freeze_map.py'"
 bash ./本机导航测试.sh stop
 bash ./本机导航测试.sh start
 echo '固定导航底图已加载；LIVO继续本轮定位，动态避障保持开启。不会自动行驶。'
 ;;
 live)
 bash ./本机导航测试.sh stop
 ssh -S "$sock" unitree@192.168.123.18 'rm -f /home/unitree/fast_livo2_port/build1/fixed_navigation_map.json'
 bash ./本机导航测试.sh start
 ;;
 stop) bash ./导航目标.sh stop; ssh -S "$sock" unitree@192.168.123.18 python3 "$board/navigation/nav2/control.py" stop;;
 status) ssh -S "$sock" unitree@192.168.123.18 python3 "$board/navigation/nav2/control.py" "$action";;
 record|list|preview|execute) exec bash ./楼层导航.sh "$@";;
 *) echo '用法: 本机导航测试.sh start/status/stop/freeze/live/record/list/preview/execute [目标名称]';exit 2;;
esac
