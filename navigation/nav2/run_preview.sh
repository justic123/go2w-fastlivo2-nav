#!/usr/bin/env bash
# 板端只读Nav2：没有SportClient，所有建议速度只发到隔离话题。
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
folder="$root/navigation/nav2"
run=${1:?run directory required}
config="$folder/preview.yaml"
if [[ -f "$root/navigation_profile" && "$(cat "$root/navigation_profile")" == floor ]];then config="$folder/floor.yaml";fi
[[ "$run" =~ ^[a-zA-Z0-9_-]+$ ]]
exec 9>"$root/nav2_preview.lock";flock -n 9 || exit 1
mkdir "$root/$run"
cp "$config" "$root/$run/nav_config.yaml"
pids=()
cleanup(){ trap - EXIT INT TERM; for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null || true; done; for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done; }
trap cleanup EXIT
trap 'exit 0' INT TERM
export OPENBLAS_NUM_THREADS=1 OMP_THREAD_LIMIT=2
# Separate shells avoid mixing ROS1/ROS2 Python and shared libraries.
env -i HOME=/home/unitree USER=unitree PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c 'source /opt/ros/noetic/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1; exec python3 "$1/input_ros1.py"' _ "$folder" > "$root/$run/input_ros1.log" 2>&1 & pids+=($!)
source /opt/ros/foxy/setup.bash
export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1
python3 "$folder/input_ros2.py" > "$root/$run/input_ros2.log" 2>&1 & pids+=($!)
/opt/ros/foxy/lib/nav2_planner/planner_server --ros-args -r __node:=planner_server --params-file "$config" > "$root/$run/planner.log" 2>&1 & pids+=($!)
/opt/ros/foxy/lib/nav2_controller/controller_server --ros-args --params-file "$config" -r cmd_vel:=/go2w_nav/proposed_cmd_vel > "$root/$run/controller.log" 2>&1 & pids+=($!)
/opt/ros/foxy/lib/nav2_lifecycle_manager/lifecycle_manager --ros-args --params-file "$config" > "$root/$run/lifecycle.log" 2>&1 & pids+=($!)
printf '%s\n' "${pids[@]}" > "$root/$run/child_pids.txt"
while true; do for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null || exit 1; done; sleep 2; done
