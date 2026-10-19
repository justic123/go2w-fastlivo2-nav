#!/usr/bin/env bash
# 建图、重定位、规划及运控均在 Go2W。电脑通过 SSH 操作菜单。
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -f board/deployment.json ]]; then
  # Quote every remote argument; names may contain spaces or shell punctuation.
  remote='bash /home/unitree/fast_livo2_port/onboard/current/板载运行.sh'
  for arg in "$@"; do printf -v quoted '%q' "$arg"; remote+=" $quoted"; done
  exec ssh -tt -o ConnectTimeout=6 -o ServerAliveInterval=2 -o ServerAliveCountMax=3 unitree@192.168.123.18 "$remote"
fi
if (( EUID != 0 )); then
  # Use the existing sudo prompt; never save passwords or add Docker group rights.
  exec sudo -H env -i HOME=/home/unitree USER=unitree PATH=/usr/bin:/bin LANG=C.UTF-8 /bin/bash "$PWD/板载运行.sh" "$@"
fi
action=${1:-menu}
case "$action" in
 speed) exec /usr/bin/python3 migration/select_speed.py "${2:-corridor04}";;
 fusion-start|fusion-status|fusion-stop) exec /usr/bin/python3 board/control.py "${action#fusion-}";;
 nav-start) /usr/bin/python3 navigation/mppi/make_config.py --output navigation/mppi/demo_nav.yaml
   exec env GO2W_MPPI_CONFIG=/work/demo_nav.yaml /usr/bin/python3 navigation/mppi/control.py start;;
 nav-status|nav-stop) exec /usr/bin/python3 navigation/mppi/control.py "${action#nav-}";;
 shutdown)
   /usr/bin/python3 demo/console.py stop
   /usr/bin/python3 navigation/mppi/control.py stop
   /usr/bin/python3 board/saved_view.py stop
   exec /usr/bin/python3 board/control.py stop;;
 power) /usr/sbin/nvpmodel -q; tail -2 /etc/nvpmodel.conf; exit;;
 *) exec /usr/bin/python3 demo/console.py "$@";;
esac
