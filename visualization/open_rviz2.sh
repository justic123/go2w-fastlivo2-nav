#!/usr/bin/env bash
set -eo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1
python3 "$folder/ros2_view.py" & view_pid=$!
trap 'kill -TERM "$view_pid" 2>/dev/null || true; wait "$view_pid" 2>/dev/null || true' EXIT
rviz2 -d "$folder/go2w_livo.rviz"
