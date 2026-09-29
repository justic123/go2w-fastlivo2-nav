#!/usr/bin/env bash
# Run through SSH: read-only, no sudo, no service start/stop, no shell profile.
set -u
run() {
  printf '\n###'
  printf ' %q' "$@"
  printf '\n'
  "$@"
  local result=$?
  printf '[exit=%s]\n' "$result"
}
run date -Is
run hostname
run uname -a
run id
run cat /etc/os-release
run cat /etc/nv_tegra_release
run free -h
run df -h / /home/unitree
run ls /opt/ros
run ip -br address
run pgrep -af 'xt16_driver|unitree_slam|keyDemo|inspection.py|inspection_bridge'
run ss -lunp
run dpkg-query -W 'nvidia-l4t-core' 'ros-noetic-*' 'libpcl-dev' 'libopencv-dev' 'libeigen3-dev'
for dir in /home/unitree/go2w_slam_setup/inspection /home/unitree/go2w_slam_setup/helpers /unitree/module/unitree_slam/config; do
  run du -sh "$dir"
done
for file in /home/unitree/test.pcd /home/unitree/go2w_slam_setup/inspection/route.json /home/unitree/go2w_slam_setup/inspection/audio_manifest.json; do
  run stat "$file"
  run sha256sum "$file"
done
