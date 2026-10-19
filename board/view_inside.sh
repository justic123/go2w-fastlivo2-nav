#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
root=$1
mode=$2
export ROS_LOCALHOST_ONLY=1 OPENBLAS_NUM_THREADS=1
export CYCLONEDDS_URI='<CycloneDDS><Domain><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>120</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>'
mkdir -p "$root/board/client"
kind=navigation
[[ "$mode" != mapping ]] || kind=mapping
exec 9>"$root/board/client/$kind.lock"
flock -n 9 || { echo '该板载视图已打开，请复用现有窗口。'; exit 1; }
if [[ "$mode" == mapping ]]; then
 export ROS_DOMAIN_ID=177 GO2W_VIEW_PORT=11335 GO2W_VIEW_STATE_DIR="$root/board/client"
 /usr/bin/python3 "$root/desktop/ros2_view.py" > "$root/board/client/mapping.log" 2>&1 & client=$!
 config="$root/visualization/go2w_live_map.rviz"
else
 export ROS_DOMAIN_ID=179
 /usr/bin/python3 "$root/board/view_client.py" > "$root/board/client/navigation.log" 2>&1 & client=$!
 config="$root/navigation/mppi/view.rviz"
 [[ "${3:-map}" != camera_init ]] || config="$root/navigation/mppi/view_mapping.rviz"
 [[ "$mode" != cloud ]] || config="$root/navigation/mppi/view_cloud.rviz"
fi
cleanup() { kill -TERM "$client" 2>/dev/null || true; wait "$client" 2>/dev/null || true; }
trap cleanup EXIT
rviz2 -d "$config" --ros-args -p use_sim_time:="$( [[ "$mode" == mapping ]] && echo false || echo true )"
