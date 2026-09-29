#!/usr/bin/env bash
set -eo pipefail
base=/home/unitree/fast_livo2_port/audit/ros-sdk-compare-01
mkdir "$base"
child=
trap 'if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi' EXIT
for n in 1 2; do
  root="$base/round-$n"; mkdir "$root"
  echo "Starting comparison $n"
  /home/unitree/fast_livo2_port/audit/build/lowstate_audit 35 > "$root/sdk.csv" 2> "$root/sdk.stderr" & child=$!
  env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin CAPTURE_OUTPUT="$root/ros" bash --noprofile --norc -c '
    source /opt/ros/foxy/setup.bash
    source /home/unitree/cyclonedds_ws/install/setup.bash
    source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
    python3 /home/unitree/fast_livo2_port/audit/src/compare_ros2_capture.py "$CAPTURE_OUTPUT"
  ' > "$root/ros.log" 2>&1
  wait "$child";child=
  echo "Completed comparison $n"
done
