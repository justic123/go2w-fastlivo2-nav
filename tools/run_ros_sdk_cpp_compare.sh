#!/usr/bin/env bash
set -eo pipefail
base=/home/unitree/fast_livo2_port/audit/ros-sdk-cpp-01
mkdir "$base"
child=
trap 'if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi' EXIT
for n in 1 2; do
  root="$base/round-$n"; mkdir -p "$root/ros"
  echo "Starting comparison $n"
  /home/unitree/fast_livo2_port/audit/build/lowstate_audit 35 > "$root/sdk.csv" 2> "$root/sdk.stderr" & child=$!
  env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin CAPTURE_OUTPUT="$root/ros" bash --noprofile --norc -c '
    source /opt/ros/foxy/setup.bash
    source /home/unitree/cyclonedds_ws/install/setup.bash
    source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
    /home/unitree/fast_livo2_port/audit/ros2_cpp_build/ros2_lowstate_audit > "$CAPTURE_OUTPUT/ros2.csv"
  ' > "$root/ros.log" 2>&1
  printf '%s\n' '{"backend":"C++ ROS2, best effort depth 100", "dog_imu_raw":"not observed by this C++ node"}' > "$root/ros/summary.json"
  wait "$child";child=
  echo "Completed comparison $n"
done
