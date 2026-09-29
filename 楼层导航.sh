#!/usr/bin/env bash
# 只有execute类命令会真实运动；preview包含长路径重规划但不发SDK。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd);sock="$HOME/.ssh/go2w-mapping.sock"
ssh -S "$sock" -O check unitree@192.168.123.18 >/dev/null 2>&1 || { echo '先运行 楼层建图.sh start';exit 1; }
action=${1:-status}
case "$action" in
 status|stop) exec bash "$folder/导航目标.sh" "$action";;
 record|list)
  # Use a JSON argv envelope; names never become shell command text.
  exec /usr/bin/python3 - "$sock" "$action" "${2:-}" <<'PY'
import json,subprocess,sys,shlex
args=['python3','/home/unitree/fast_livo2_port/build1/navigation/nav2/places.py',sys.argv[2]]
if sys.argv[2]=='record':args.append(sys.argv[3])
raise SystemExit(subprocess.call(['ssh','-S',sys.argv[1],'unitree@192.168.123.18',' '.join(shlex.quote(x) for x in args)]))
PY
  ;;
 preview|execute)
  [[ -n "${2:-}" ]] || { echo '指定已记录地点名称';exit 2; }
  exec /usr/bin/python3 "$folder/navigation/nav2/laptop_goal.py" "$action" --floor --named-goal "$2";;
 relative-preview|relative-execute)
  exec /usr/bin/python3 "$folder/navigation/nav2/laptop_goal.py" "${action#relative-}" "${2:?前方米数}" "${3:-0}" --floor;;
 map-preview|map-execute)
  exec /usr/bin/python3 "$folder/navigation/nav2/laptop_goal.py" "${action#map-}" "${2:?地图X}" "${3:?地图Y}" --floor --map-goal --yaw "${4:-0}";;
 *) echo '用法: 楼层导航.sh record/list/preview/execute/status/stop；坐标模式relative-preview/relative-execute/map-preview/map-execute';exit 2;;
esac
