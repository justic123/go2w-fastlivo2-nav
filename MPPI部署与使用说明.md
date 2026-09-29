# 本机 Nav2＋MPPI 部署与使用

本版本保留 FAST-LIVO2，独立部署 ROS2 Humble Nav2＋MPPI。已完成虚拟机器人闭环测试和真实传感器影子测试；`start`、`preview`、`shadow` 均不驱动机器狗，只有显式 `return-execute` 执行受保护实机返回。`shadow` 输出候选速度，不是自动行驶。旧板端 DWB 文件保持原状，可回退。

工作目录：`/home/river/文档/ChatGPT/巡检/fast_livo2_port`

## 启动

```bash
cd /home/river/文档/ChatGPT/巡检/fast_livo2_port
# 初次部署/换电脑需构建镜像；需要 Docker，但不修改宿主机 ROS 安装。
bash MPPI导航.sh build
# 机器人正常站立、静止；若本机 FAST-LIVO2 已 ready，无需重复执行。
bash 本机建图测试.sh start
bash MPPI导航.sh start
bash MPPI导航.sh check
bash MPPI导航.sh rviz
```

`start` 复用正在运行的本模式实例，不会再次建立地图。`check` 验证四个 Nav2 生命周期节点 active，以及当前输入的新鲜度。只有 `running=true` 不能代替 `check`。若等待输入超时，查看 `navigation/mppi/current.json` 指向的日志目录。机器人重启或 FAST-LIVO2 新建图后，旧坐标目标失效，须停止 MPPI 并重新启动绑定新会话。

## 规划和候选速度检查

以下坐标是本轮 `camera_init` 地图中的绝对坐标，单位米、弧度。不要使用前一轮地图坐标。

```bash
bash MPPI导航.sh preview 1.0 0.0 0.0
# 8 秒影子控制：真实机器人不动，因此不要期待它完成到点任务。
bash MPPI导航.sh shadow 1.0 0.0 0.0
bash MPPI导航.sh status
bash MPPI导航.sh stop
```

`stop` 只停止本版本 MPPI 和其专属 ROS1 数据导出，不停止 FAST-LIVO2，也不会调用旧导航的运动测试。实机返回入口为 `return-execute`，使用统一足迹检查、看门狗和到位验收；不应使用 `ros2 topic pub /cmd_vel` 绕过。

## 不依赖机器狗的虚拟闭环测试

```bash
bash MPPI导航.sh stop
bash MPPI导航.sh simulation
bash MPPI导航.sh check
bash MPPI导航.sh sim-goal 0.8 0.0 0.5
bash MPPI导航.sh stop
```

仿真用理想平面速度积分、房间边界点云，不模拟轮足动力学、转向伴随平移、真实制动或传感器噪声。误差只说明软件链路是否闭合，不代表实机精度。

## RViz

独立窗口使用 ROS_DOMAIN_ID=79、Fixed Frame=`camera_init`。
- Global costmap：导航当前感知的障碍和可通行区域。
- Planned path：全局规划路径。
- Robot pose：TF 中 `go2w_mppi_base` 为融合位姿参考点。
- Current lidar：实时雷达点云；这不是彩色累计地图。

原来的彩色 FAST-LIVO2 窗口仍属于域 77，可同时查看；不要把两个 ROS 域的窗口混淆。当前 MPPI RViz 没有直接发运动目标的工具。

## 架构和参数

ROS1 源 `/go2w_lio/odometry`、`/go2w_lio/points`、`/clock` → 本机回环 TCP 11339 → Humble 域79 → NavFn/A* → MPPI → velocity_smoother → `/mppi/cmd_vel_smoothed`（仅候选，无 SDK 订阅者）。

不新增雷达/IMU驱动；不修改任何传感器标定；不修改系统时间。保留 FAST-LIVO2 原始时间戳与 `/clock`，另用单调时钟检查断流。输入过期持续 0.5 秒后退出整套 MPPI 服务；收到数据也不能把旧传感器时间戳改为“现在”。

首版：20Hz 控制、40×0.05s 预测、1000候选、1次迭代；候选前进0–0.2m/s、倒退最多0.1m/s，侧移0，角速度±0.8rad/s。DiffDrive 只代表本次允许的平面指令空间，并不表示 Go2W 的硬件是差速轮式底盘。候选控制开放小范围倒退以验证末端位置修正；实机倒退尚未开放。侧移仍为零。

位置容差8cm、朝向0.12rad是验收配置，**不是已达到的实机精度**。GoalAngleCritic 在12cm邻域参与，避免距目标较远就强行对准最终朝向，产生横向偏差。该阈值只经过简化仿真，后续需结合实机调整。目标检查 `stateful=false`，同时检查位置和朝向；旧 `terminal_control.py`、起步转向、反复位置恢复均不在新链路内。

平滑器 `feedback=OPEN_LOOP` 指用上一次输出估计速度斜坡起点，导航本身仍然使用真实融合位姿闭环；不是用速度×时间估计行驶距离。后续应在实测速度反馈可靠后比较 CLOSED_LOOP。

## 为什么不整套照搬 BotBrain

BotBrain 可用，但其 RTABMap、外加相机、Web/任务管理并非本次所需。审阅的 Go2W 配置中 MPPI 允许侧移，而平滑器侧向限速为零；速度转发回调还过滤全零速度。因此本项目采用 Nav2 官方 Humble 软件包，独立验证配置一致性，保留既有显式停车机制的设计。

上游参考：
- https://github.com/ros-navigation/navigation2/tree/humble/nav2_mppi_controller
- https://github.com/botbotrobotics/BotBrain/blob/main/botbrain_ws/src/go2w_pkg/config/nav2_params.yaml

## 回退和迁移

先 `bash MPPI导航.sh stop`；然后按原来的 `本机导航测试.sh` 启动旧板端 DWB。不要在同一次运动测试同时启动两套运动出口。

笔记本需 Ubuntu22.04、Docker、原 FAST-LIVO2 迁移环境。拷贝项目（不用拷贝 `navigation/mppi/runs`），重新构建镜像；入口按脚本所在目录定位文件，不依赖桌面机绝对路径。安装 ROS2 Humble RViz 后可打开可视化。镜像首次构建需要联网，已构建后启动不需要联网。

## 本次验证记录（2026-09-29）

- 已安装 Nav2/MPPI 1.1.20 的 Humble 二进制包；具体包版本与镜像 ID 见 `navigation/mppi/installed_versions.txt`。
- 参数跨层一致性检查4项通过；独立容器重启、重复start复用、单一ROS1导出进程检查通过。
- 虚拟目标 `(0.8,0,0.5rad)`：Nav2成功结束；结束前位姿估计误差7.56cm、0.109rad；取消/结束后候选速度归零。**仅理想仿真，不代表Go2W实机精度。**
- 暂停虚拟输入进程后，监护程序检测到输入停止更新并退出所有Nav2子进程。记录中input.json内部可能仍写ready=true，但文件本身过期，因此整体拒绝继续运行。
- 真实数据影子目标 `(0.60,-0.39,-2.16rad)`：规划成功，8秒约160条平滑候选速度（20Hz），按预定时限取消，随后全零。机器人未受控运动，不能将此结果称为实机到达成功。
- 初次真实输入暴露点云接收问题：可靠订阅约59–60帧/6秒，但Best Effort约7帧/6秒。导航副本采用5cm体素过滤后，约61600点降到14500点，Best Effort达到60帧/6秒。此结果定位到消息体积/QoS相关的接收问题，尚未证明底层DDS丢包的唯一机制。
- 对导航点云增加短队列等待融合TF覆盖原始采样时间；不刷新时间戳、不改变标定。
- 最新真实运行窗口中，全局/局部代价地图没有记录observation过期告警、控制器没有记录missed-rate告警；长期表现与实际绕障仍待运动测试。

证据在 `navigation/mppi/runs/`：`simulation-20260929-123242` 为虚拟闭环及断流退出；`live-20260929-123827-1540572` 为最终真实输入影子验证。新地图会话为 `desktop-20260929-122604`，旧地图目标不可复用。

最后20秒健康采样：100/100输入与生命周期就绪；位姿数据年龄中位数0.265s、最大0.276s；点云年龄中位数0.277s、最大0.307s。此延迟仍需在实机闭环前评估，不能宣称已完全消除。

## 2026-09-29：复用旧地图与返回精度试验

已选择 `room-20260928` 固定地图，原始建图会话 `desktop-20260928-230235`。旧二维地图与对应时刻前的注册点云保存在 `navigation/mppi/maps/room-20260928/`。当前 FAST-LIVO2 会话通过 `map → camera_init` 变换定位到旧地图；本轮局部里程计仍连续运行。不能停止 FAST-LIVO2 后继续依赖实时定位。

`selection.json` 的变换严格绑定当前建图会话。重启 FAST-LIVO2 后不能照搬旧变换，必须重新匹配并验证。Nav2 全局规划使用 `map`，局部代价地图使用 `camera_init`，机身正前方为 `go2w_mppi_base` 的 +X。雷达坐标轴不代表机头方向。

两个窗口用途不同：

- 彩色建图窗口：本轮 FAST-LIVO2 点云与轨迹；黄色箭头直接取当前融合位姿，断流约0.6秒后消失。修复前箭头来自已停止的旧导航服务，会残留旧位姿。
- 旧地图导航窗口：固定地图、当前点云与重定位结果；橙红色 `ROBOT FORWARD (+X)` 表示机身正前方。不要依据屏幕上下比较两个窗口，视角和世界坐标原点可能不同；要对照同一墙面或门。

一键启动当前已配置会话的导航服务，不发送运动：

```bash
cd /home/river/文档/ChatGPT/巡检/fast_livo2_port
bash MPPI导航.sh start
bash MPPI导航.sh status
bash MPPI导航.sh rviz
```

精度试验顺序：

1. 重定位与输入健康均为 `ready`，确认箭头方向与现场相符。在地面标记同一机身参考点，并用两点记录原始朝向。
2. 静止记录目标：`bash MPPI导航.sh record 精度返回点`。程序检查约3.5秒静止数据，保存位置、朝向、地图及会话编号。
3. 遥控离开标记点约0.8–1米后停稳，保证路线及线缆可用。
4. `bash MPPI导航.sh return-preview`：规划并最多运行8秒MPPI预演，板端保护程序不初始化DDS、不调用SportClient，机器人不运动。
5. 预演通过且现场有人接管时，`bash MPPI导航.sh return-execute`：5秒倒计时后执行单次返回；最长90秒。按Ctrl+C可取消。接近障碍或表现异常时直接遥控接管。
6. 停稳后不要挪动机器狗，量同一参考点到标记点的纵向、横向误差，并用原始方向标记核对朝向误差。记录是否发生接管。不能用融合位姿自身误差代替卷尺结果。

运动链路为 Nav2 NavigateToPose → MPPI → velocity_smoother → 输入/定位/足迹检查 → 本机UNIX接口 → SSH → 板端独立保护程序 → SportClient.Move。没有按“速度×时间”推算距离的控制步骤；目标判断使用实时地图坐标中的融合定位。当前限制前进0.20m/s、后退0.10m/s、角速度0.8rad/s，目标容差8cm和0.12rad（约6.9°）；这是配置容差，不是已经验证的实机精度。

板端保护沿用运动互斥锁 `point_trial.lock`。Twist消息本身不携带生成时间；保护层保留首次接收该指令的单调时钟时刻，SSH转发不重新打时间戳，时钟握手采用保守偏移；超过150ms的指令拒绝，断流300ms独立停车。结束或异常时先关闭运动出口，再取消Nav2动作。地图匹配失败、输入过期、定位跳变或足迹碰撞检查失败都不能继续运动。

底层单独启动与检查入口：

- 导航管理：`python3 navigation/mppi/control.py start|status|stop`。
- 目标记录：`docker exec go2w-nav2-mppi python3 /work/record.py 精度返回点`。
- 完整无运动预演：`python3 navigation/mppi/run_protected.py`。
- 板端保护无运动回归：`python3 navigation/mppi/test_guard_transport.py`，覆盖正反向合法指令、过期拒绝和断流停车。
- 受保护运动由 `run_protected.py --execute` 统一管理；不要手动绕过它向底层SportClient发送速度。

结果位于 `navigation/mppi/current.json` 指向的目录：`accuracy_target.json`、`localization.json`、`protected-preview-*.json`、`protected-execute-*.json`、`motion-commands-*.jsonl`。`success` 只表示实机执行满足软件条件；`preview_passed` 表示无运动链路预演通过；`ground_truth` 未填写时，没有外部测量精度结论。

### 末端低速修订（2026-09-29 15:46）

两轮实机末端持续输出约0.055–0.065m/s而几乎不移动。单独增加低速惩罚在模拟中仍失败；将PathAngleCritic的threshold_to_consider从0.5m改为0.12m，并使用VelocityDeadbandCritic（deadband_velocities=[0.08,0,0]、cost_weight=35）后，带假设0.075m/s线速度死区的虚拟机器人完成往返：位置约7.9cm/4.4cm、朝向约4.8°/6.0°，输出归零。这不是实机精度结论，也不代表已标定真实死区。

低速惩罚在轨迹评分内生效，不能保证每条输出均超过0.08m/s；没有在输出端强制抬升速度。最高速度、足迹、8cm/0.12rad目标容差及停车保护保持原值。原配置与原返回目标备份于`navigation/mppi/experiments/deadband-20260929/live-backup`；虚拟测试结果在同级candidate/state与state-deadband-only。

官方插件实现参考：[Nav2 Humble VelocityDeadbandCritic](https://api.nav2.org/nav2-humble/html/velocity__deadband__critic_8cpp_source.html)。下一次实机执行前须先return-preview，并核对地面标记和接管条件。

### 指令时钟换算修订与实机阶段结果

一次实机中，板端拒绝年龄为-0.000690秒的指令；实测两端单调时钟偏移在每2秒内变化约0.5–0.7毫秒。保护传输现每2秒重新握手，并从偏移下界额外扣除3毫秒，让换算时间更保守。指令保留保护层首次接收时刻，板端150ms过期和300ms断流保护不变。`test_guard_clock.py`在无SDK的preview模式验证运行期间校准及未来时间拒绝；原过期/断流回归仍通过。

修订后的一次实机返回进入末端，融合估计位置误差0.103m、朝向误差0.0091rad（约0.5°），因定位或代价地图接收超时保护停车，SDK StopMove返回0。仍未满足8cm位置容差，不能记为成功，现场卷尺与朝向结果待核对。未自动继续补走。接收超时现补充独立的位姿/代价地图接收年龄，便于区分后续原因。
