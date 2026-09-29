#!/usr/bin/env bash
set -eo pipefail
base=/home/unitree/fast_livo2_port/audit/multiround-20260927-01
if pgrep -x xt16_driver >/dev/null || pgrep -x unitree_slam >/dev/null; then
  echo 'Driver/SLAM already running; abort to avoid duplicate publishers.' >&2; exit 1
fi
mkdir "$base"
driver_pid= imu_pid=
cleanup() {
  for child in "$imu_pid" "$driver_pid"; do
    if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT
for round in 1 2 3; do
  root="$base/round-$round"
  mkdir "$root"
  echo "Starting round $round: 60-second full point-cloud capture"
  timeout -s INT -k 5 75 bash /home/unitree/go2w_slam_setup/helpers/run_driver.sh > "$root/driver.log" 2>&1 & driver_pid=$!
  sleep 2
  timeout -s TERM -k 3 70 /home/unitree/fast_livo2_port/audit/build/lowstate_audit 65 > "$root/lowstate.csv" 2> "$root/lowstate.stderr" & imu_pid=$!
  env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin ROUND_OUTPUT="$root/lidar" bash --noprofile --norc -c '
    source /opt/ros/foxy/setup.bash
    source /home/unitree/cyclonedds_ws/install/setup.bash
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
    python3 /home/unitree/fast_livo2_port/audit/src/capture_inputs.py --save-all --seconds 60 --topic /unitree/slam_lidar/points --output "$ROUND_OUTPUT"
  ' > "$root/capture.log" 2>&1
  wait "$imu_pid"; imu_pid=
  kill -TERM "$driver_pid" 2>/dev/null || true
  wait "$driver_pid" 2>/dev/null || true
  driver_pid=
  if pgrep -x xt16_driver >/dev/null; then echo 'Driver did not stop'; exit 1; fi
  echo "Completed round $round"
done
