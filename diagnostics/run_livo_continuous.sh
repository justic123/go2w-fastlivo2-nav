#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
run=${1:?output directory name required}
reference=${2:?start or end required}
seconds=0
max_radius=20
if [[ -f "$root/navigation_profile" && "$(cat "$root/navigation_profile")" == floor ]];then max_radius=95;fi
imu_source=ros2
[[ "$imu_source" =~ ^(ros2|sdk2)$ ]]
exec 9>"$root/continuous_capture.lock"
flock -n 9 || { echo "Capture already active"; exit 1; }
[[ "$run" =~ ^[a-zA-Z0-9_-]+$ && "$reference" =~ ^(start|end)$ ]]
if pgrep -x xt16_driver >/dev/null || pgrep -x unitree_slam >/dev/null || pgrep -x fastlivo_mapping >/dev/null; then echo 'Conflicting process'; exit 1; fi
mkdir "$root/$run"
cp "$root/mapping/livo_display_candidate.yaml" "$root/$run/livo_config.yaml"
cp "$root/camera/livo_diagnostic/camera_candidate.yaml" "$root/$run/camera_config.yaml"
stop_requested=false
bridge_pid= monitor_pid=
master_pid= node_pid= driver_pid= camera_pid= decode_pid= view_pid= bag_pid=
cleanup() {
  trap - INT TERM
  if [[ -n "$bridge_pid" ]]; then kill -TERM "$bridge_pid" 2>/dev/null || true; wait "$bridge_pid" 2>/dev/null || true; fi
  if [[ -n "$monitor_pid" ]]; then kill -TERM "$monitor_pid" 2>/dev/null || true; wait "$monitor_pid" 2>/dev/null || true; fi
  if [[ -n "$bag_pid" ]]; then kill -INT "$bag_pid" 2>/dev/null || true; wait "$bag_pid" 2>/dev/null || true; fi
  for child in "$view_pid" "$camera_pid" "$decode_pid" "$node_pid" "$master_pid" "$driver_pid"; do
    if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
  done
  mkdir -p "$root/$run/state_logs"
  cp "$root/ws/src/FAST-LIVO2/Log/"{mat_pre.txt,mat_out.txt} "$root/$run/state_logs/" 2>/dev/null || true
}
trap cleanup EXIT
request_stop() {
  stop_requested=true
  [[ -z "$bridge_pid" ]] || kill -TERM "$bridge_pid" 2>/dev/null || true
}
trap request_stop INT TERM
export OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1
source /opt/ros/noetic/setup.bash
source "$root/ws/devel/setup.bash"
export ROS_MASTER_URI=http://127.0.0.1:11321 ROS_IP=127.0.0.1 ROS_HOSTNAME=localhost ROS_LOG_DIR="$root/$run/ros_logs"
roscore -p 11321 > "$root/$run/master.log" 2>&1 & master_pid=$!
ready=false
for attempt in {1..20}; do
  if rosparam list >/dev/null 2>&1; then ready=true; break; fi
  sleep .5
done
[[ "$ready" == true ]]
rosbag record --lz4 --buffsize=256 -O "$root/$run/sensors.bag" /go2w_lio/points /go2w_lio/imu /go2w_lio/cloud /go2w_lio/odometry /go2w_livo/jpeg > "$root/$run/bag.log" 2>&1 & bag_pid=$!
python3 "$root/mapping/ros1_view_source.py" > "$root/$run/view.log" 2>&1 & view_pid=$!
rosparam load "$root/mapping/livo_display_candidate.yaml" /go2w_lio
rosparam load "$root/camera/livo_diagnostic/camera_candidate.yaml" /go2w_lio/laserMapping
rosrun fast_livo fastlivo_mapping __ns:=/go2w_lio /aft_mapped_to_init:=/go2w_lio/odometry /cloud_registered:=/go2w_lio/cloud /path:=/go2w_lio/path /mavros/vision_pose/pose:=/go2w_lio/unused_pose > "$root/$run/node.log" 2>&1 & node_pid=$!
bash /home/unitree/go2w_slam_setup/helpers/run_driver.sh > "$root/$run/driver.log" 2>&1 & driver_pid=$!
python3 "$root/mapping/decode_jpeg.py" "$root/$run/image_summary.json" 0 > "$root/$run/decode.log" 2>&1 & decode_pid=$!
"$root/mapping/jpeg_build/livo_jpeg" _duration_sec:=0 > "$root/$run/jpeg.log" 2>&1 & camera_pid=$!
python3 "$root/mapping/mapping_bridge.py" --imu-source "$imu_source" --diagnostic --point-time-unit ns --header-reference "$reference" --seconds "$seconds" --max-radius "$max_radius" --output "$root/$run/bridge" & bridge_pid=$!
if [[ "$stop_requested" == true ]]; then kill -TERM "$bridge_pid" 2>/dev/null || true; fi
# Stop input if a pipeline child dies or disk has less than 5 GiB free.
( while kill -0 "$bridge_pid" 2>/dev/null; do
    for child in "$node_pid" "$driver_pid" "$camera_pid" "$decode_pid" "$bag_pid" "$view_pid"; do
      if ! kill -0 "$child" 2>/dev/null; then echo "Pipeline child exited: $child"; kill -TERM "$bridge_pid"; exit 1; fi
    done
    free_kb=$(df -Pk "$root" | awk 'NR==2 {print $4}')
    if (( free_kb < 5242880 )); then echo "Disk reserve reached"; kill -TERM "$bridge_pid"; exit 1; fi
    sleep 2
  done ) > "$root/$run/monitor.log" 2>&1 & monitor_pid=$!
rc=0
while kill -0 "$bridge_pid" 2>/dev/null; do if wait "$bridge_pid"; then rc=0; else rc=$?; fi; done
bridge_pid=
echo "Bridge finished, rc=$rc"
quality_rc=0
python3 "$root/check_imu_continuity.py" "$root/$run/bridge/imu_timing.csv" "$root/$run/imu_quality.json" || quality_rc=$?

cleanup
trap - EXIT
export_rc=0
python3 "$root/mapping/export_map.py" "$root/$run" > "$root/$run/map_export.log" 2>&1 || export_rc=$?
rgb_rc=0
rgb_voxel=.02
[[ "$max_radius" != 95 ]] || rgb_voxel=.05
python3 "$root/mapping/export_rgb_map.py" "$root/$run" --voxel "$rgb_voxel" > "$root/$run/rgb_map_export.log" 2>&1 || rgb_rc=$?
python3 - "$root/$run/completion.json" "$rc" "$quality_rc" "$export_rc" "$rgb_rc" <<'PYEND'
import sys,json
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps(dict(bridge_exit=int(sys.argv[2]),imu_check_exit=int(sys.argv[3]),map_export_exit=int(sys.argv[4]),rgb_map_export_exit=int(sys.argv[5]))))
PYEND
