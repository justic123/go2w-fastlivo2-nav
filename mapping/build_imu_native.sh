#!/usr/bin/env bash
# Run on Go2W with ROS1 Noetic installed; output is architecture-specific.
set -eo pipefail
source /opt/ros/noetic/setup.bash
cd -- "$(dirname -- "$0")"
g++ -O2 -std=c++14 imu_forward_native.cpp -o imu_forward_native $(pkg-config --cflags --libs roscpp)
