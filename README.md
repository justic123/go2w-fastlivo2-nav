# Go2W FAST-LIVO2 + Nav2 MPPI

Go2W 轮足机器人的激光／惯性／视觉建图与导航实验项目：FAST-LIVO2 提供融合位姿和点云，Nav2 MPPI 负责路径跟踪，运动指令通过宇树高层 SportClient 执行。

Experimental mapping and navigation integration for the Unitree Go2W, using FAST-LIVO2 localization and Nav2 MPPI control. This repository contains integration code, reproducible dependency revisions, diagnostics and Chinese operating documentation. It is not an official Unitree release or a turnkey robot firmware image.

## 当前能力与边界

- 交互式扫图、保存地图、记录目标、路径预演和显式启动导航。
- 保存地图的自动匹配与 RViz `2D Pose Estimate` 辅助重定位；匹配失败会阻止导航。
- 彩色点云、灰度膨胀障碍图、路线和机头朝向可视化。
- 多途经点按顺序执行，每点停稳后再进入下一点；异常取消剩余路线。
- 传感器时效检查、限速、通信看门狗、地图匹配校验和短时数据积压恢复。

曾完成房间绕椅子演示和单轮约7cm的实测返回。该数值不是跨场地精度保证。多点任务已有离线／仿真验证，长距离实机、长时间时钟稳定性和跨楼层导航尚未验收。2026-09-30 的断流修复通过了故障注入和60秒连续输入检查；同轮自动旧地图重定位未通过，仍需辅助定位。

可回退的实测参数标签：`v0.1.1-measured-return-20260929`。`main` 提供当前实验代码；标签保留历史参数与原有验证范围。

## 系统结构

```text
Go2W：XT16 数据链路 + LowState IMU + 原装前置相机
    │  板端采集、格式适配、SSH 转发
    ▼
Ubuntu PC：FAST-LIVO2（ROS1 / Docker）
    │  融合位姿、点云与时间信息
    ▼
ROS2 Humble：保存地图定位 + Nav2 / MPPI + RViz
    │  受保护的高层速度指令、超时停车
    ▼
Go2W：SportClient
```

当前主要验证方式是 PC 运行算法、板端运行采集和运控桥接。板端独立运行的历史入口也保留，但不能把两套入口同时启动。使用原装广角相机，不要求安装 RealSense；相机标定与传感器时间参数需按实际机器复核。

## 获取与部署

建议主机为 Ubuntu 22.04、ROS2 Humble，安装 Docker；使用千兆有线连接进行初次验证。

```bash
git clone https://github.com/justic123/go2w-fastlivo2-nav.git
cd go2w-fastlivo2-nav
# 下载固定版本依赖并应用补丁；只恢复源码，不启动机器人。
python3 dependencies/restore.py
```

本仓库尚未提供从空白系统到整机可运行的一条命令安装器。脚本仍包含原测试环境的目录、网卡名、IP及容器名称；请先阅读 [部署前检查](OPEN_SOURCE_SETUP.md)，完成路径调整、板端驱动与 SDK 准备、容器构建和 SSH 主机身份确认。公开仓库不包含地图、原始录包、机器人固件、Docker 镜像和登录凭据。

**完成部署后**使用交互入口：

```bash
bash 演示控制台.sh
```

推荐流程：新建图 → 保存地图 → 核对定位 → 添加目标／路线 → 路径预演 → 明确选择导航。已有地图选择恢复定位，无需重新扫图。看到路径不代表已经启动运动；重定位失败时显示的旧地图也不代表定位成功。

## 使用文档

| 任务 | 文档 |
| --- | --- |
| 交互菜单、单点、多点及 RViz 辅助重定位 | [交互演示控制台](交互演示控制台使用说明.md) |
| Nav2 MPPI、单独启动与故障检查 | [MPPI 部署与使用](MPPI部署与使用说明.md) |
| 更换为笔记本、网络与环境 | [笔记本迁移](笔记本迁移与使用说明.md) |
| 版本与参数回退 | [版本管理](版本管理与回退.md) |
| 绕障演示 | [Demo 使用与拍摄](绕障Demo使用与拍摄说明.md) |
| 传感器中断 | [断流修复与验证范围](desktop/传感器断流修复_20260930.md) |
| 早期适配和阶段性测试 | [历史记录](HISTORY.md) |

历史文档中的 `evidence/` 链接和绝对路径是原工作环境的记录，不是公开下载链接。以当前交互文档为操作入口。

## 无硬件测试

安装 `python3-numpy`、`python3-yaml` 后，在仓库根目录执行：

```bash
PYTHONPATH=demo:navigation/mppi python3 -m unittest discover -s demo -p 'test_*.py'
python3 -m unittest discover -s desktop -p test_backlog_policy.py
python3 -m unittest discover -s desktop -p test_transport_buffer.py
python3 -m unittest discover -s navigation/mppi -p test_config.py
```

上述41项测试不发送运动指令。实机测试应另行记录现场距离、角度与接管情况；SLAM 自报误差不能替代外部测量。运行 `navigate`、`execute` 或菜单5/16会产生实际运动，首次运行应由现场人员保持遥控接管。

## 开源与贡献

原创适配和导航编排代码采用 [MIT](LICENSE)；第三方源码、参考文件和补丁按各自许可证提供，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。FAST-LIVO2、Vikit 等组件不因本仓库的 MIT 许可证而改变授权条件。

欢迎通过 Issue 报告可复现问题，通过 Pull Request 提交改进。请阅读 [贡献说明](CONTRIBUTING.md)，不要上传密码、室内地图或未经处理的相机图像。
