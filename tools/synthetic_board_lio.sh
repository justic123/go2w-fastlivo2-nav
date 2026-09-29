#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
source /opt/ros/noetic/setup.bash
source "$root/ws/devel/setup.bash"
export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1 ROS_HOSTNAME=localhost
export ROS_LOG_DIR="$root/synthetic_logs"
mkdir -p "$ROS_LOG_DIR"
master_pid= node_pid=
cleanup() {
  if [[ -n "$node_pid" ]]; then kill -INT "$node_pid" 2>/dev/null || true; wait "$node_pid" || true; fi
  if [[ -n "$master_pid" ]]; then kill -INT "$master_pid" 2>/dev/null || true; wait "$master_pid" || true; fi
}
trap cleanup EXIT
roscore -p 11321 > "$root/synthetic_master.log" 2>&1 & master_pid=$!
ready=false
for attempt in {1..20}; do
  if rosparam list >/dev/null 2>&1; then ready=true; break; fi
  sleep 0.5
done
[[ "$ready" == true ]]
rosparam load "$root/startup_smoke_only.yaml" /smoke
rosrun fast_livo fastlivo_mapping __ns:=/smoke > "$root/synthetic_node.log" 2>&1 & node_pid=$!
/usr/bin/python3 "$root/synthetic_lio.py"
kill -0 "$node_pid"
