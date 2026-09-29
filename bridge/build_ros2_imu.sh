#!/usr/bin/env bash
set -eo pipefail
root=/home/unitree/fast_livo2_port/build1
source /opt/ros/foxy/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
source /home/unitree/fast_livo2_port/ros2_compare_ws/install/setup.bash
cmake -S "$root/bridge/ros2_imu_source" -B "$root/ros2_imu_build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$root/ros2_imu_build" -j2
