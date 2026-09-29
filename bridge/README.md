# Go2W XT16 + LowState 在线诊断适配

执行于机器人Orin NX，ROS2点云订阅与ROS2 C++ IMU订阅（默认，可显式回退SDK2）在独立进程，ROS1进程将转换后的传感器消息发布给FAST-LIVO2。没有导航或运动命令。

- `ros2_imu_source/`：C++订阅`/lowstate`，逐条刷新输出，沿用tick时间锚定；运行上限120秒。
- `cloud_source_ros2.py`：只订阅XT16原始点云，使用私有Unix socket传输原始payload及schema。
- `input_core.py`：严格检查22字节点格式，过滤非法点，稳定按点时间排序，转换float64秒timestamp；LowState tick去重及时间锚定。
- `live_bridge_ros1.py`：等待算法订阅就绪；先等待IMU发现和500个有效tick预热，再启动点云订阅，固定接收时间中位数锚点；按扫描时间区间缓冲IMU后发布。8帧点云队列、4000条IMU缓冲；缺IMU超时丢帧、tick倒退/回绕和大时钟偏离停止并记录。它不是经过标定的硬件同步器。
- `candidate.yaml`：官方Rz(+90°)/[0.171,0,0.0908]初值，关闭相机。滤点间隔4，体素0.2米；噪声参数未标定。
- `run_board_diagnostic.sh`：启动独立localhost:11321 ROS master、算法、驱动；只运行5～60秒并清理。输出在板端build1/指定目录；目录必须尚不存在。

输入话题：`/go2w_lio/points`、`/go2w_lio/imu`；诊断输出：`/go2w_lio/odometry`、`/go2w_lio/cloud`。这些话题位于独立ROS1 master，不自动接入既有导航系统。

## 板端复现

首次构建C++入口：使用干净环境执行 `bash /home/unitree/fast_livo2_port/build1/bridge/build_ros2_imu.sh`。依赖已隔离安装的官方 `unitree_go` 消息包（`ros2_compare_ws`），无需修改系统ROS。运行脚本第四参数默认 `ros2`，可选 `sdk2` 用于对照。

```bash
env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin \
  timeout -k 5 110 bash --noprofile --norc \
  /home/unitree/fast_livo2_port/build1/bridge/run_board_diagnostic.sh \
  new-diagnostic-run end 60 ros2
```

`end`或`start`必须显式指定，脚本内部显式启用`--diagnostic --point-time-unit ns`。这只是候选时间约定，不代表已确认宇树驱动时间语义。没有设置开机启动。完整运行以summary.json和进程退出状态为准；达到最少输出数量并不代表丢帧、精度或实时性能验收通过。

## 源码核查

- FAST-LIVO2的XT32预处理要求float64秒timestamp，将相对时间换为毫秒curvature；同步器用点云末点时间决定扫描结束，因此需要正确排序。
- 禾赛官方SDK `CalcXTPointXYZIT`从包时间生成点timestamp，并叠加微秒级block/laser偏移（除以1e6）；`realtime`分支则使用包接收时间。`EmitBackMessege`将首点timestamp作为回调参数。该源码没有说明宇树封装后float32 time与header的转换。
- `unitreerobotics/unitree_slam` commit `1e49bfa4dca2c992a566ee7d1d8480d4102149b8`仍为接口例程/消息和库；未找到当前XT16驱动封装实现。
- 官方SDK2 LowState提供uint32 tick；此适配按文档1ms建立候选时间轴，不能从IDL类型得出准确雷达时钟映射。

官方来源：
- https://github.com/HesaiTechnology/HesaiLidar_General_SDK
- https://github.com/unitreerobotics/unitree_slam
- https://github.com/unitreerobotics/unitree_sdk2
- https://github.com/hku-mars/FAST-LIVO2

## 尚未验收

点时间单位/header基准、未知IMU采样延迟、输入坐标方向与动态去畸变仍需验证。接收时间锚定会包含传输延迟；当前只固定初始锚点，不持续估计漂移，因此脚本限制为短时诊断。tick回绕/重启会停止，不能直接用于长期任务。最终应取得同版本封装实现或进行有依据的时间/外参验证，再扩展为持续运行。
