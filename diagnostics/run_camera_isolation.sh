#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
run=${1:-camera-isolation-01}
[[ "$run" =~ ^[a-zA-Z0-9_-]+$ ]]
out=$root/$run
mkdir "$out"
ros_pid= sdk_pid= camera_pid=
cleanup(){ for p in "$camera_pid" "$ros_pid" "$sdk_pid"; do if [[ -n "$p" ]]; then kill -TERM "$p" 2>/dev/null || true; wait "$p" 2>/dev/null || true; fi; done; }
trap cleanup EXIT
cat /proc/net/snmp > "$out/net_before.txt"
/home/unitree/fast_livo2_port/audit/build/lowstate_audit 78 > "$out/sdk.csv" 2> "$out/sdk.stderr" & sdk_pid=$!
env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin bash --noprofile --norc -c '
 source /opt/ros/foxy/setup.bash
 source /home/unitree/cyclonedds_ws/install/setup.bash
 source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash
 export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
 exec /home/unitree/fast_livo2_port/build1/mapping/imu_build/ros2_imu_source 78
' > "$out/ros.csv" 2> "$out/ros.stderr" & ros_pid=$!
sleep 3
"$root/camera_load_build/camera_load" > "$out/camera.csv" 2> "$out/camera.stderr" & camera_pid=$!
wait "$camera_pid";camera_pid=
wait "$ros_pid";ros_pid=
wait "$sdk_pid";sdk_pid=
cat /proc/net/snmp > "$out/net_after.txt"
