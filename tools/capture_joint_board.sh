#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/audit/joint-20260927-01
if pgrep -x xt16_driver >/dev/null || pgrep -x unitree_slam >/dev/null; then
  echo 'Existing driver or SLAM process; abort isolated capture.' >&2; exit 1
fi
mkdir "$root"
timeout -s INT -k 5 25 bash /home/unitree/go2w_slam_setup/helpers/run_driver.sh > "$root/driver.log" 2>&1 & driver_pid=$!
trap 'kill -INT "$driver_pid" 2>/dev/null || true; wait "$driver_pid" 2>/dev/null || true' EXIT
sleep 2
/home/unitree/fast_livo2_port/audit/build/lowstate_audit > "$root/lowstate.csv" 2> "$root/lowstate.stderr" & imu_pid=$!
env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin bash --noprofile --norc -c '
source /opt/ros/foxy/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
python3 /home/unitree/fast_livo2_port/audit/src/capture_inputs.py --seconds 15 --topic /unitree/slam_lidar/points --output /home/unitree/fast_livo2_port/audit/joint-20260927-01/lidar
' > "$root/capture.log" 2>&1
wait "$imu_pid"
