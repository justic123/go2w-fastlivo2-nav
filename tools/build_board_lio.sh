#!/usr/bin/env bash
# Fresh isolated build. Stage source-final.tar.gz in an otherwise empty root first.
set -eo pipefail
root=${1:-/home/unitree/fast_livo2_port/build-repro}
cd "$root"
[[ ! -e ws && ! -e Sophus ]] || { echo 'Use a fresh build directory' >&2; exit 1; }
tar -xzf source-final.tar.gz
mkdir -p ws/src
mv FAST-LIVO2 ws/src/
mv rpg_vikit/vikit_common rpg_vikit/vikit_ros ws/src/
mv vision_opencv/cv_bridge ws/src/
# Normalize only newly staged files to this host clock; do not change system time.
find Sophus ws/src -type f -exec touch {} +
cmake -S Sophus -B sophus_build -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build sophus_build -j2
(cd sophus_build && ctest --output-on-failure)
source /opt/ros/noetic/setup.bash
cd ws
catkin_make -j2 -l2 -DSophus_DIR="$root/sophus_build" -DPYTHON_EXECUTABLE=/usr/bin/python3 -DCMAKE_BUILD_TYPE=Release
