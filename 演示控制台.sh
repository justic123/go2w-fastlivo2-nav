#!/usr/bin/env bash
# 默认中文菜单；仅明确选择navigate/菜单5时启用运动。
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec /usr/bin/python3 demo/console.py "$@"
