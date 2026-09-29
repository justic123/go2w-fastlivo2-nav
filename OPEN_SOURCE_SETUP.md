# 公开仓库部署前检查

本项目从一套实际 Go2W 环境整理而来，当前发布的是源码和操作记录，不是即插即用产品。已有测试机不需要因开源发布重新部署。

1. **获取依赖**：在仓库根目录运行 `python3 dependencies/restore.py`。下载位置、commit 和补丁哈希由 `dependencies/sources.json` 固定；脚本跳过已存在的非空目录。Vikit 源码随仓库提供，保留其GPL声明。
2. **主机准备**：Ubuntu 22.04、ROS2 Humble、Docker、NumPy、PyYAML。先阅读《笔记本迁移与使用说明》和《MPPI部署与使用说明》。不要假设原电脑已有的容器或构建产物随 Git 下载。
3. **主机算法构建**：`bash desktop/build.sh` 构建 Noetic 容器和算法工作区；`navigation/mppi/Dockerfile` 为 ROS2/Nav2 镜像入口，镜像命名和启动参数以 MPPI 文档为准。源码恢复/构建不等于板端部署已经完成。
4. **板端前提**：具备对应雷达驱动、ROS、Unitree SDK 和 SSH 访问。测试环境板端根目录为 `/home/unitree/fast_livo2_port/build1`，主机原目录为 `/home/river/文档/ChatGPT/巡检/fast_livo2_port`，IP为 `192.168.123.18`。这是示例环境，不是对任何机器人都有效的设置。按文档逐项调整，避免用未经检查的全仓库替换。
5. **转发模块部署**：本机模式的 `desktop/raw_source.py`、`desktop/backlog_policy.py`、`desktop/transport_buffer.py` 需一起安装到板端 `build1/lifecycle/`。`desktop/raw_receiver.py` 由主机容器挂载。更新文件后由对应主管正常重启，不另起重复驱动。
6. **标定与硬件**：本项目测试的是 XT16 数据链路、机身 LowState IMU 和原装前置相机。Go2/Go2W 社区相机参数只是候选；检查坐标系、外参、分辨率和采样时间，不能直接把所有参考文件视为本机真值。
7. **先不运动验证**：保持静止初始化，检查传感器、处理延迟及 RViz 的机器人朝向。先完成路径预演，再由现场操作员明确启动运动。参考菜单10做辅助重定位；不能跳过匹配校验。

## 私有运行资料

以下资料由使用者自行生成，不随开源仓库分发：室内地图、目标点与路线状态、图像、录包、日志、SSH认证信息、机器人固件、编译后的SDK库及Docker镜像。示例文档记录的测试数值可以保留，实际现场图像和地图不要自动上传。

## 版本

- `main`：公开的当前实验版本。
- `codex/navigation-optimization`：开发与修复分支。
- `v0.1.0-baseline-20260929` / `v0.1.1-measured-return-20260929`：原始实验基线；标签不等于全部新功能已经通过实机验收。
