# 板端 Nav2 无运动集成

入口：本机 `../../导航预演.sh start|status|plan|stop`，完整操作见 `../../RViz与导航使用说明.md`。

该目录无SportClient调用。DWB输出只重映射到 `/go2w_nav/proposed_cmd_vel`，仅显示导出节点和测试客户端订阅。不要将其直接改名为运控订阅话题。

## 数据与进程

- `input_ros1.py`：读当前ROS1雷达/里程计。10cm点云降采样只用于导航桥；通过板内/dev/shm原子快照发送，不走笔记本网络。雷达视野不受RGB相机视角限制。
- `input_ros2.py`：Foxy域78发布PointCloud2、Odometry和TF；时间戳保留板端源时间，不重打时间掩盖延迟。外参沿用LIVO候选参数。状态文件原子替换，避免读取到半个JSON。
- `preview.yaml`：Navfn A*、DWB、ObstacleLayer、InflationLayer。滚动局部地图，不加载持久地图，也不实现AMCL/回环。未知区不可规划。
- `run_preview.sh`：板端拥有全部子进程，退出时只停止它们；不停止LIVO。旧Foxy规划器默认名为nav2_planner，这里显式重命名为planner_server匹配生命周期及参数。
- `control.py`：文件锁与PID出生时间校验，避免重复启动/误杀旧PID。
- `plan_probe.py`：前方相对目标≤5m；先检查数据新鲜度，只请求路径，可采样3秒隔离建议速度后取消。输出actuation_enabled=false。取消状态5是预期取消，不代表运动到点成功。
- `local_view.py`：本机Humble域77，SSH转发11327接收显示数据，只发布显示话题。11325原LIVO显示链路保留。
- `test_planner.py`：独立域79，合成空旷/障碍/封路场景，真实Navfn插件验证，不连接机器人传感器或SDK。

## 当前验收边界

软件规划和无运动DWB输出已验证；候选足迹/高度筛选、传感器时间同步、局部状态更新频率、动态障碍、负障碍、窄通道、运控闭环均未完成实机验收。当前速度可能低于实机有效起步速度，不能直接通过增加最低速度绕过验证。需要全机身尺寸测量及受控运动验收后，才可增加真实运控出口。不能宣称已支持长距离自动或跨楼层。

当前20×20m滚动全局代价地图中的“全局”是Nav2组件名，不代表全楼层或持久全局地图。用户的长距离需求还需要地图重定位和长程漂移评估。
