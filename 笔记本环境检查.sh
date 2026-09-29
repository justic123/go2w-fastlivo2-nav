#!/usr/bin/env bash
# 仅本机依赖检查，不连接机器人、不安装软件、不发运动指令。
set -eo pipefail
source /etc/os-release
printf '系统: %s\n' "$PRETTY_NAME"
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 22.04 ]] || { echo '本迁移包按Ubuntu22.04验证，请先核对兼容性。';exit 1; }
command -v ssh >/dev/null
[[ -r /opt/ros/humble/setup.bash ]] || { echo '缺少ROS2 Humble，请按迁移文档安装。';exit 1; }
env -i HOME="$HOME" USER="${USER:-user}" PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c '
source /opt/ros/humble/setup.bash
command -v rviz2
python3 - <<"PY"
import rclpy,numpy,PIL
from sensor_msgs.msg import Image,PointCloud2
from nav_msgs.msg import Path,OccupancyGrid
print("ROS2/Python/NumPy/Pillow依赖可用")
PY
'
if [[ -z "${DISPLAY:-}" ]];then echo '当前没有DISPLAY；请在笔记本图形桌面的终端启动RViz。';exit 1;fi
printf 'DISPLAY=%s\n' "$DISPLAY"
echo '本机依赖检查通过；网线、SSH、实际画面仍需现场验证。'
