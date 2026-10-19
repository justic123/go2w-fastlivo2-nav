#!/usr/bin/env bash
# Compile a separately staged native release on the robot; never replace live code.
set -euo pipefail
release=${1:?pass a new absolute FAST-LIO2 release directory}
[[ "$release" = /* && -f "$release/ws/src/FAST_LIO/CMakeLists.txt" && -f "$release/fastlio.yaml" ]]
[[ ! -e "$release/ws/build" && ! -e "$release/ws/devel" ]] || { echo 'Use a fresh release directory'; exit 1; }
free=$(df --output=avail -B1 "$release" | tail -1)
(( free > 6*1024*1024*1024 )) || { echo 'Need 6 GiB build reserve'; exit 1; }
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 OMP_THREAD_LIMIT=4 OMP_WAIT_POLICY=PASSIVE
set +u
source /opt/ros/noetic/setup.bash
set -u
cd "$release/ws"
catkin_make -j1 -l2 -DPYTHON_EXECUTABLE=/usr/bin/python3 -DCMAKE_BUILD_TYPE=Release \
  -DCATKIN_ENABLE_TESTING=OFF -DGO2W_WITH_LIVOX=OFF -DGO2W_MP_THREADS=4 -DGO2W_BUILD_CHECKS=ON
set +u
source devel/setup.bash
set -u
devel/lib/fast_lio/go2w_xt16_check
