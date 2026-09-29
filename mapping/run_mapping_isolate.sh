#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
run=${1:?output directory name required}
reference=${2:?start or end required}
seconds=${3:-180}
imu_source=${4:-ros2}
[[ "$imu_source" =~ ^(ros2|sdk2)$ ]]
[[ "$seconds" =~ ^[0-9]+$ ]] && (( seconds >= 5 && seconds <= 180 ))
[[ "$run" =~ ^[a-zA-Z0-9_-]+$ && "$reference" =~ ^(start|end)$ ]]
if pgrep -x xt16_driver >/dev/null || pgrep -x unitree_slam >/dev/null || pgrep -x fastlivo_mapping >/dev/null; then echo 'Conflicting process'; exit 1; fi
mkdir "$root/$run"
master_pid= node_pid= driver_pid= camera_pid= decode_pid= view_pid= bag_pid=
cleanup() {
  if [[ -n "$bag_pid" ]]; then kill -INT "$bag_pid" 2>/dev/null || true; wait "$bag_pid" 2>/dev/null || true; fi
  for child in "$view_pid" "$camera_pid" "$decode_pid" "$node_pid" "$master_pid" "$driver_pid"; do
    if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT
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
rosbag record --buffsize=256 -O "$root/$run/sensors.bag" /go2w_lio/points /go2w_lio/imu /go2w_lio/cloud /go2w_lio/odometry /go2w_livo/jpeg > "$root/$run/bag.log" 2>&1 & bag_pid=$!

rosparam load "$root/mapping/livo_display_candidate.yaml" /go2w_lio
rosparam load "$root/camera/livo_diagnostic/camera_candidate.yaml" /go2w_lio/laserMapping
rosrun fast_livo fastlivo_mapping __ns:=/go2w_lio /aft_mapped_to_init:=/go2w_lio/odometry /cloud_registered:=/go2w_lio/cloud /path:=/go2w_lio/path /mavros/vision_pose/pose:=/go2w_lio/unused_pose > "$root/$run/node.log" 2>&1 & node_pid=$!
timeout -s INT -k 5 "$((seconds+25))" bash /home/unitree/go2w_slam_setup/helpers/run_driver.sh > "$root/$run/driver.log" 2>&1 & driver_pid=$!
python3 "$root/mapping/decode_jpeg.py" "$root/$run/image_summary.json" > "$root/$run/decode.log" 2>&1 & decode_pid=$!
"$root/mapping/jpeg_build/livo_jpeg" > "$root/$run/jpeg.log" 2>&1 & camera_pid=$!
python3 "$root/mapping/mapping_bridge.py" --imu-source "$imu_source" --diagnostic --point-time-unit ns --header-reference "$reference" --seconds "$seconds" --output "$root/$run/bridge"
kill -0 "$node_pid"
kill -0 "$camera_pid"
kill -0 "$decode_pid"
kill -0 "$bag_pid"
