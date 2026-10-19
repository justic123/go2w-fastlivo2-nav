# Go2W FAST-LIVO2 + Nav2 MPPI

Go2W 轮足机器人的激光／惯性／视觉建图与导航实验项目：FAST-LIVO2 提供融合位姿和点云，Nav2 MPPI 负责路径跟踪，运动指令通过宇树高层 SportClient 执行。

Experimental mapping and navigation integration for the Unitree Go2W, using FAST-LIVO2 localization and Nav2 MPPI control. This repository contains integration code, reproducible dependency revisions, diagnostics and Chinese operating documentation. It is not an official Unitree release or a turnkey robot firmware image.

## 当前能力与边界

- 交互式扫图、保存地图、记录目标、路径预演和显式启动导航。
- 保存地图的自动匹配、网页位置/朝向提示、固定位置辅助重定位；匹配失败会阻止导航。
- 彩色点云、灰度膨胀障碍图、路线和机头朝向可视化。
- 多途经点按顺序执行，每点停稳后再进入下一点；异常取消剩余路线。
- 板端网页显示二维代价图、三维点云、广角相机与路线；Mac/Windows/Linux 可作为浏览器操作端。
- 同一地图和定位会话内，停止任务可重新预演剩余路线，再显式继续。
- 传感器时效检查、限速、通信看门狗、地图匹配校验和短时数据积压恢复。

曾完成房间绕椅子演示和单轮约7cm的实测返回。该数值不是跨场地精度保证。2026-10-18已有板端5Hz融合与Nav2共载、旧图定位和多点任务完成记录；末端微小速度导致无进展停车仍待优化。长距离持续运行及跨楼层导航尚未验收。普通越障模式切换已在本机原地核对，不代表自动上下连续楼梯已经实现。

可回退的实测参数标签：`v0.1.1-measured-return-20260929`。`main` 提供当前实验代码；标签保留历史参数与原有验证范围。

## 系统结构

```text
Go2W：XT16 数据链路 + LowState IMU + 原装前置相机
    │  板端采集、格式适配
    ▼
Go2W 板载：FAST-LIVO2（ROS1 原生）
    │  融合位姿、点云与时间信息
    ▼
Go2W 板载 ROS2 Humble 容器：保存地图定位 + Nav2 / MPPI
    │  受保护的高层速度指令、超时停车
    ▼
Go2W：SportClient

Go2W 网页后台 ← 网线 HTTP → Mac / Windows / Linux 浏览器
```

当前使用板端独立运行，电脑只显示网页并提交受控操作。网页正常使用无需在电脑安装ROS、RViz或Docker。旧PC计算与Ubuntu/RViz入口仍作为历史对照保留，不能与板端入口同时启动。使用原装广角相机，不要求安装 RealSense；相机标定与传感器时间参数需按实际机器复核。

## 获取与部署

**当前已部署机器人**：电脑配置机器人网段后打开 **http://192.168.123.18:8088/**，按[网页流程](board/web/README.md)操作。换Mac见[Mac网线控制与操作说明](Mac网线控制与操作说明.md)，无需迁移Docker镜像。板端统一目录为 `/home/unitree/fast_livo2_port/onboard/current`。

**从源码新部署或复现旧PC方案**：下面命令仅获取源码。旧PC方案使用Ubuntu22.04、ROS2 Humble和Docker；板端部署使用ARM64原生融合与导航容器，两者不能混用镜像。首次联调使用千兆有线连接。

```bash
git clone https://github.com/justic123/go2w-fastlivo2-nav.git
cd go2w-fastlivo2-nav
# 下载固定版本依赖并应用补丁；只恢复源码，不启动机器人。
python3 dependencies/restore.py
```

本仓库尚未提供从空白系统到整机可运行的一条命令安装器。脚本仍包含原测试环境的目录、网卡名、IP及容器名称；请先阅读 [部署前检查](OPEN_SOURCE_SETUP.md)，完成路径调整、板端驱动与 SDK 准备、容器构建和 SSH 主机身份确认。公开仓库不包含地图、原始录包、机器人固件、Docker 镜像和登录凭据。

已部署机器人可直接使用网页；若使用终端交互，在板端统一目录运行：

```bash
bash 板载运行.sh
```

网页与终端菜单共享操作锁，同一时间只使用一种控制入口。网页任务依赖持续续约，断联超过5秒会请求停车，恢复网络后需明确重新预演和继续。

推荐流程：新建图 → 保存地图 → 核对定位 → 添加目标／路线 → 路径预演 → 明确选择导航。已有地图选择恢复定位，无需重新扫图。看到路径不代表已经启动运动；重定位失败时显示的旧地图也不代表定位成功。

## 使用文档

| 任务 | 文档 |
| --- | --- |
| 当前板载部署与运行入口 | [板载说明](board/README.md) |
| 网页扫图、定位、目标、路线与相机 | [网页工作台](board/web/README.md) |
| 更换 Mac，网线直连和完整流程 | [Mac操作说明](Mac网线控制与操作说明.md) |
| 停止后继续未完成路线 | [任务恢复](board/停止后继续任务说明_20261018.md) |
| 地面固定标记辅助重定位 | [固定位置重定位](board/固定位置重定位使用说明.md) |
| 交互菜单、单点、多点及 RViz 辅助重定位 | [交互演示控制台](交互演示控制台使用说明.md) |
| Nav2 MPPI、单独启动与故障检查 | [MPPI 部署与使用](MPPI部署与使用说明.md) |
| 旧PC计算方案的Ubuntu笔记本迁移 | [历史笔记本迁移](笔记本迁移与使用说明.md) |
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

这些隔离测试不发送运动指令。实机测试应另行记录现场距离、角度与接管情况；SLAM 自报误差不能替代外部测量。运行 `navigate`、`execute` 或菜单5/16会产生实际运动，首次运行应由现场人员保持遥控接管。

## 开源与贡献

原创适配和导航编排代码采用 [MIT](LICENSE)；第三方源码、参考文件和补丁按各自许可证提供，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。FAST-LIVO2、Vikit 等组件不因本仓库的 MIT 许可证而改变授权条件。

欢迎通过 Issue 报告可复现问题，通过 Pull Request 提交改进。请阅读 [贡献说明](CONTRIBUTING.md)，不要上传密码、室内地图或未经处理的相机图像。
