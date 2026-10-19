#!/usr/bin/env bash
# UI and all robot algorithms run on Go2W; this client only uses SSH.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -f board/deployment.json ]]; then
  remote='bash /home/unitree/fast_livo2_port/onboard/current/网页控制台.sh'
  for arg in "$@"; do printf -v quoted '%q' "$arg"; remote+=" $quoted"; done
  exec ssh -tt -o ConnectTimeout=6 unitree@192.168.123.18 "$remote"
fi
if (( EUID != 0 )); then
  exec sudo -H env -i HOME=/home/unitree USER=unitree PATH=/usr/bin:/bin LANG=C.UTF-8 bash "$PWD/网页控制台.sh" "$@"
fi
case "${1:-status}" in
 install)
  python3 board/web/install.py;;
 start) systemctl start go2w-web.service;;
 stop) systemctl stop go2w-web.service;;
 restart) systemctl restart go2w-web.service;;
 status) systemctl --no-pager status go2w-web.service;;
 key) printf '网页地址：http://192.168.123.18:8088\n网页访问码：'; cat board/web-state/access-key; printf '\n';;
 *) printf '用法：bash 网页控制台.sh install|start|stop|restart|status|key\n'; exit 2;;
esac
