#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
base=$root/load-lio-only-01
mkdir "$base"
ros_pid= sdk_pid= job_pid=
cleanup() {
 for pid in "$job_pid" "$ros_pid" "$sdk_pid"; do
  if [[ -n "$pid" ]]; then kill -TERM "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
 done
}
trap cleanup EXIT
for stage in algorithm; do
 dir=$base/$stage;mkdir "$dir"
 cat /proc/net/snmp > "$dir/net_before.txt"
 date +%s.%N > "$dir/start.txt"
 /home/unitree/fast_livo2_port/audit/build/lowstate_audit 48 > "$dir/sdk.csv" 2> "$dir/sdk.stderr" & sdk_pid=$!
 env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin bash --noprofile --norc -c '
 source /opt/ros/foxy/setup.bash
 source /home/unitree/cyclonedds_ws/install/setup.bash
 source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash
 export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0 CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
 exec /home/unitree/fast_livo2_port/build1/mapping/imu_build/ros2_imu_source 48
 ' > "$dir/ros.csv" 2> "$dir/ros.stderr" & ros_pid=$!
 sleep 3
 case "$stage" in
 lidar) timeout -s INT -k 5 35 bash /home/unitree/go2w_slam_setup/helpers/run_driver.sh > "$dir/driver.log" 2>&1 & job_pid=$! ;;
 algorithm) bash "$root/run_lio_capture.sh" load-lio-clean-01 end 30 ros2 > "$dir/job.log" 2>&1 & job_pid=$! ;;
 display) bash "$root/mapping/run_board_mapping_view.sh" load-display-01 end 30 ros2 > "$dir/job.log" 2>&1 & job_pid=$! ;;
 esac
 if [[ -n "$job_pid" ]]; then
  set +e;wait "$job_pid";status=$?;set -e;printf '%s\n' "$status" > "$dir/job_exit.txt";job_pid=
 fi
 wait "$ros_pid";ros_pid=
 wait "$sdk_pid";sdk_pid=
 cat /proc/net/snmp > "$dir/net_after.txt"
 echo "Completed $stage"
done
