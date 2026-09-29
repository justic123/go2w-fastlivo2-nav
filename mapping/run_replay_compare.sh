#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
mode=${1:?lio or livo}; run=${2:?new output directory}
variant=${3:-baseline}
bag_run=${4:-manual-map-07}
window=${5:-100}
rate=${6:-0.5}
[[ "$bag_run" =~ ^[a-zA-Z0-9_-]+$ ]]
if pgrep -x fastlivo_mapping >/dev/null; then echo "Algorithm already running"; exit 1; fi
[[ "$variant" =~ ^(baseline|rotation0|rotation_minus90|imu_plus100ms|imu_minus100ms|imuoff|dense1|dense2|dense2_surf5|dense4|image_minus50ms|image_minus100ms|dense2_image_minus100ms)$ ]]
[[ "$mode" == lio || "$mode" == livo ]]
[[ "$run" =~ ^[a-zA-Z0-9_-]+$ ]]
mkdir "$root/$run"
export OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1
source /opt/ros/noetic/setup.bash
source "$root/ws/devel/setup.bash"
export ROS_MASTER_URI=http://127.0.0.1:11331 ROS_IP=127.0.0.1 ROS_HOSTNAME=localhost ROS_LOG_DIR="$root/$run/ros_logs"
master_pid= node_pid=
cleanup() {
 for child in "$node_pid" "$master_pid"; do
  if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
 done
 mkdir -p "$root/$run/state_logs"
 cp "$root/ws/src/FAST-LIVO2/Log/"{mat_pre.txt,mat_out.txt,imu.txt} "$root/$run/state_logs/" 2>/dev/null || true
}
trap cleanup EXIT
roscore -p 11331 > "$root/$run/master.log" 2>&1 & master_pid=$!
ready=false
for attempt in {1..30}; do
 if rosparam list >/dev/null 2>&1; then ready=true; break; fi
 sleep .3
done
[[ "$ready" == true ]]
rosparam set /use_sim_time true
rosparam load "$root/mapping/livo_replay_baseline.yaml" /go2w_lio
if [[ "$mode" == lio ]]; then rosparam set /go2w_lio/common/img_en 0; fi
rosparam load "$root/camera/livo_diagnostic/camera_candidate.yaml" /go2w_lio/laserMapping
case "$variant" in
 dense2_image_minus100ms) rosparam set /go2w_lio/preprocess/point_filter_num 2; rosparam set /go2w_lio/preprocess/filter_size_surf 0.1; rosparam set /go2w_lio/time_offset/img_time_offset -0.1 ;;
 dense1) rosparam set /go2w_lio/preprocess/point_filter_num 1; rosparam set /go2w_lio/preprocess/filter_size_surf 0.1 ;;
 dense2_surf5) rosparam set /go2w_lio/preprocess/point_filter_num 2; rosparam set /go2w_lio/preprocess/filter_size_surf 0.05 ;;
 dense2) rosparam set /go2w_lio/preprocess/point_filter_num 2; rosparam set /go2w_lio/preprocess/filter_size_surf 0.1 ;;
 dense4) rosparam set /go2w_lio/preprocess/point_filter_num 4; rosparam set /go2w_lio/preprocess/filter_size_surf 0.1 ;;
 image_minus50ms) rosparam set /go2w_lio/time_offset/img_time_offset -0.05 ;;
 image_minus100ms) rosparam set /go2w_lio/time_offset/img_time_offset -0.1 ;;
 imuoff) rosparam set /go2w_lio/imu/imu_en false ;;
 rotation0) rosparam set /go2w_lio/extrin_calib/extrinsic_R '[1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0]' ;;
 rotation_minus90) rosparam set /go2w_lio/extrin_calib/extrinsic_R '[0.0,1.0,0.0,-1.0,0.0,0.0,0.0,0.0,1.0]' ;;
 imu_plus100ms) rosparam set /go2w_lio/time_offset/imu_time_offset -0.1 ;;
 imu_minus100ms) rosparam set /go2w_lio/time_offset/imu_time_offset 0.1 ;;
esac
printf '%s\n' "$variant" > "$root/$run/variant.txt"
rosparam dump "$root/$run/params.yaml"
rosrun fast_livo fastlivo_mapping __ns:=/go2w_lio /aft_mapped_to_init:=/go2w_lio/odometry /cloud_registered:=/go2w_lio/cloud /path:=/go2w_lio/path /mavros/vision_pose/pose:=/go2w_lio/unused_pose > "$root/$run/node.log" 2>&1 & node_pid=$!
python3 "$root/mapping/replay_compare.py" "$root/$bag_run/sensors.bag" "$root/$run" "$mode" "$window" "$rate"
kill -0 "$node_pid"
