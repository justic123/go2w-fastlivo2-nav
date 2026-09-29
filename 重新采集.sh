#!/usr/bin/env bash
set -euo pipefail
# start: leave an existing session running. restart: save it, then start fresh.
umask 077
mkdir -p "$HOME/.ssh"
action=${1:-restart}
case "$action" in start|restart|stop|status) ;; *) echo '用法: bash 重新采集.sh [restart|start|stop|status]'; exit 2;; esac
if [[ "$action" == start || "$action" == restart ]]; then
  if ! ssh -S "${HOME}/.ssh/go2w-mapping.sock" -O check unitree@192.168.123.18 >/dev/null 2>&1; then
    ssh -M -S "${HOME}/.ssh/go2w-mapping.sock" -o ControlPersist=12h -o ServerAliveInterval=2 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o ConnectTimeout=5 -fN -L 127.0.0.1:11325:127.0.0.1:11325 unitree@192.168.123.18
  fi
fi
run="livo-manual-$(date +%Y%m%d-%H%M%S)-$RANDOM"
timeout --foreground 45s ssh -S "${HOME}/.ssh/go2w-mapping.sock" -o ConnectTimeout=5 unitree@192.168.123.18 python3 /home/unitree/fast_livo2_port/build1/capture_control.py "$action" "$run"
