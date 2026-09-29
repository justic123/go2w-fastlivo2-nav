#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
if ! pgrep -f '^(/usr/bin/)?python3 .*/desktop/ros2_view.py$' >/dev/null;then
 setsid -f env -i HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin LANG=C.UTF-8 GO2W_VIEW_PORT=11335 bash -c 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1; exec python3 "$1/desktop/ros2_view.py"' _ "$root" > "$root/desktop/logs/display.log" 2>&1 < /dev/null &
fi
if ! pgrep -f '^(/usr/bin/)?python3 .*/navigation/nav2/local_view.py$' >/dev/null;then
 setsid -f env -i HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1; exec python3 "$1/navigation/nav2/local_view.py"' _ "$root" > "$root/desktop/logs/nav_view.log" 2>&1 < /dev/null &
fi
if ! pgrep -f '^rviz2 -d .*/visualization/go2w_live_map.rviz' >/dev/null;then
 setsid -f env -i HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin LANG=C.UTF-8 DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" bash -c 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1; exec rviz2 -d "$1/visualization/go2w_live_map.rviz"' _ "$root" > "$root/desktop/logs/rviz.log" 2>&1 < /dev/null &
fi
