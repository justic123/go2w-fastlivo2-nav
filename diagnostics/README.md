# 输入完整性与取图干扰诊断

2026-09-27：两轮独立试验证实，在本机配置下 GetImageSample 请求期间 LowState 观测 tick 缺口显著增多，停图窗口恢复。当前优先用不发起相机请求的 LIO 入口，不能只在算法中设 img_en=0 却继续取图。

推荐入口（已同步板端 build1 根目录）：
- `run_lio_capture.sh <新目录名> end 30 ros2`：雷达＋IMU，录包，无相机请求，无显示。
- `run_lio_display_capture.sh <新目录名> end 30 ros2`：同上，加现有单向显示转发。

`end` 仍是未完成物理验证的帧头假设；以上入口不等于动态精度验收。两者使用独立 ROS1 master 11321，并在退出时清理自己启动的进程，正常收尾录包。新目录必须不存在。

新增 `check_imu_continuity.py` 检查 tick 连续性：至少500条、无倒退、最大间隔不超过20ms；这是暂定的保守诊断门槛，不是厂家指标或导航安全保证。数据仍保存，检查未通过则启动脚本返回失败。旧运动录包 max=226ms、166次>20ms，应判输入质量不合格。

`run_load_matrix.sh` 是首次分组试验，algorithm组包含相机且启动即中止，不能称为成功的算法稳态负载组。`run_lio_load.sh`、`run_lio_display_load.sh` 补测真正不取图的LIO负载。监测程序各运行48秒，算法输入30秒，统计窗口不要混淆。

`camera_load` 为独立SDK读取程序：初始化后10–30秒5Hz取图，40–60秒1Hz取图，中间和前后不请求；无雷达、算法、ROS图像发布、解码、显示或落盘JPEG。只记录请求耗时和长度。`run_camera_isolation.sh <新目录名>` 同时采集独立SDK/ROS2 IMU日志，之后用 `analyze_camera_isolation.py` 比较固定窗口。

这些脚本不发送运动命令。不要将原带相机的 mapping/run_board_mapping_view.sh 当作当前动态LIO基线入口。
