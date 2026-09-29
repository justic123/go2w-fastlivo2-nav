#!/usr/bin/env bash
# 独立 Nav2 + MPPI。start不运动，return-execute显式开启单次受保护返回。
set -eo pipefail
cd -- "$(dirname -- "$0")"
action=${1:-status}
case "$action" in
 build) docker build -t go2w-nav2-mppi:humble navigation/mppi;;
 start|simulation|stop|status) exec /usr/bin/python3 navigation/mppi/control.py "$action";;
 check|preview|shadow|sim-goal)
 shift
 exec docker exec go2w-nav2-mppi bash -c 'source /opt/ros/humble/setup.bash; exec python3 /work/probe.py "$@"' _ "$action" "$@";;
 record) exec docker exec go2w-nav2-mppi python3 /work/record.py "${2:-精度返回点}";;
 return-preview) exec /usr/bin/python3 navigation/mppi/run_protected.py;;
 return-execute)
 echo "返回已记录位置及朝向。请保留遥控接管，确保路线和线缆余量；5秒内Ctrl+C可取消。"
 for n in 5 4 3 2 1; do echo "$n"; sleep 1; done
 exec /usr/bin/python3 navigation/mppi/run_protected.py --execute "${@:2}";;
 rviz)
 exec env -i HOME="$HOME" USER="$USER" DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=79 ROS_LOCALHOST_ONLY=1; export CYCLONEDDS_URI="<CycloneDDS><Domain><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>120</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>"; exec rviz2 -d "$2" --ros-args -p use_sim_time:=true' _ "$PWD" "${2:-$PWD/navigation/mppi/view.rviz}";;
 *) echo '用法: MPPI导航.sh build|start|simulation|status|check|stop|rviz|preview x y yaw|shadow x y yaw|sim-goal x y yaw';exit 2;;
esac
