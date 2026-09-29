#!/usr/bin/env bash
set -eo pipefail
root=$(cd -- "$(dirname -- "$0")" && pwd)
docker build -t go2w-livo-desktop:20260928 "$root"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:/work" go2w-livo-desktop:20260928 bash -c '
set -e
cmake -S /work/Sophus -B /work/sophus_build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON
cmake --build /work/sophus_build -j4
source /opt/ros/noetic/setup.bash
cd /work/ws
catkin_make -j4 -l6 -DSophus_DIR=/work/sophus_build -DPYTHON_EXECUTABLE=/usr/bin/python3 -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=OFF
'
