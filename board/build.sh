#!/usr/bin/env bash
# Build an already staged release on the board. Never writes the live workspace.
set -euo pipefail
release=${1:?pass an absolute release directory}
base=${GO2W_BOARD_BASE:-/home/unitree/fast_livo2_port/build1}
[[ "$release" = /* && "$release" != "$base" && -f "$release/ws/src/FAST-LIVO2/board-source-manifest.json" ]]
[[ ! -e "$release/ws/build" && ! -e "$release/ws/devel" ]] || { echo 'Use a new release directory'; exit 1; }
free=$(df --output=avail -B1 "$release" | tail -1)
(( free > 6*1024*1024*1024 )) || { echo 'Insufficient build reserve'; exit 1; }
# Source trees are copied to avoid changing original calibration, logs or sources.
for package in vikit_common vikit_ros cv_bridge; do
  cp -a "$base/ws/src/$package" "$release/ws/src/$package"
done
find "$release/ws/src" -type f -exec touch {} +
set +u
source /opt/ros/noetic/setup.bash
set -u
cd "$release/ws"
catkin_make -j2 -l2 -DSophus_DIR="$base/sophus_build" -DPYTHON_EXECUTABLE=/usr/bin/python3 \
  -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=OFF -DGO2W_WITH_CUDA=ON
