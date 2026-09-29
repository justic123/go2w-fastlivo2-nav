#!/usr/bin/env bash
# 仅恢复本机显示，不改变板端采集和地图。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
exec env -u LD_LIBRARY_PATH -u LD_PRELOAD /usr/bin/python3 "$folder/visualization/start_view.py"
