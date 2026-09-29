#!/usr/bin/env bash
# 启动服务不运动；只有显式导航目标execute会运动。
set -euo pipefail
folder=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$folder"
case "${1:-start}" in
 start)
  echo '新建图初始化时请保持静止，等本命令返回成功后再遥控扫图。'
  bash ./重新采集.sh start
  bash ./导航预演.sh start
  echo '服务已启动。当前不会运动；另开终端使用 导航目标.sh preview/execute。'
  exec /usr/bin/python3 ./visualization/start_view.py;;
 status)
  bash ./重新采集.sh status
  bash ./导航预演.sh status
  bash ./导航目标.sh status;;
 stop)
  bash ./导航目标.sh stop
  # 先等待运动目标退出，再停止导航和采集；故障时不假装停止成功。
  for i in {1..20};do
   state=$(bash ./导航目标.sh status)
   if /usr/bin/python3 -c 'import sys,json;sys.exit(1 if json.loads(sys.argv[1]).get("running") else 0)' "$state";then
    rc=0
    bash ./导航预演.sh stop || rc=1
    bash ./重新采集.sh stop || rc=1
    bash ./关闭本机显示接收.sh || rc=1
    exit "$rc"
   fi
   sleep .5
  done
  echo '目标尚未退出，请现场接管并检查。';exit 1;;
 *) echo '用法: 一键启动.sh [start|status|stop]';exit 2;;
esac
