# Go2W 板载导航工程交接：供 Mac 上的 Codex 继续开发

> **2026-10-19晚：网页按钮问题已修复，当前仍有原厂占用**
>
> 用户确认此前中途移动，16:58的位姿变化有现场解释。机器人18:51重启后，其他SSH会话运行xt16_driver PID3219与unitree_slam PID3230，19:23两次网页新扫图初始化因此被互斥保护拒绝。两张地图由网页移入回收站，当前maps为空，未擅自恢复或清空。
>
> 修复确认框沿用旧yes导致Esc被误判为同意、无地图仍可点加载、任务只报笼统错误，以及启动前缺少可读占用检查。页面直接显示占用者并禁用无效启动；原互斥和安全门禁保留。265项板端隔离回归＋1项Mac打包检查、JS与隔离真实浏览器确认/Esc检查通过。只重载网页后台，原厂程序保持运行，未初始化融合或发送运动。详见 `board/网页按钮问题修复_20261019.md`，证据 `board/evidence/web-buttons-20261019/`，备份 `board/backups/web-buttons-20261019/`。此前17点ready记录已过期，启动前仍须核对原厂占用与现场静止状态。

> **2026-10-19 17:00前后网页联调增补**
>
> 用户确认新场地不使用旧图，并授权停止原厂驱动、静止初始化。网页实测“开始新扫图→结束保存→记录目标→单点保护预演→两点路线保存与预演”通过；新图 `demo-20261019-165225-709906688`，融合 `board-20261019-165128-10621`，导航 `live-20261019-165227-11678`。当前状态仍须核验新鲜度。修复无视觉相机重连/旧帧显示、保存新图后下拉框选旧图，以及回放验收缺口。260项Python与JS检查通过。
>
> 完整共载180秒3498样本不健康0，位姿/点云源年龄最大0.158/0.246秒；原地1轮及3.21m远点3轮execute=false预演通过，共457条指令发送前最大63.1ms。两点纯规划预演约2.27m＋2.25m通过。期间现场位姿变化约1.4m，原起点不可达的路线被正确拒绝，移动原因待现场确认。测试地图仅静止可见范围；真实运动和终点精度未验收，所有助手发起测试均无SDK执行。
>
> 旧地图几何与7个目标坐标保留；详见 `board/FAST-LIO2网页联调_20261019.md`、证据 `board/evidence/web-fastlio2-20261019/`、备份 `board/backups/web-fastlio2-20261019/`。下面16:30启动失败状态已被本次实测取代，不能继续当当前状态。

> **2026-10-19 FAST-LIO2 切换增补：当前就绪必须重新核验**
>
> 实际设备绑定已切换官方 FAST-LIO2 独立 release `onboard-iterations/fastlio2-20261019`，关闭视觉与连续录包，原生IMU实际路径仍为 `build1/mapping`。原 FAST-LIVO2 源码基线分支 `codex/onboard-fastlivo2-snapshot-20261019`（8bce45a），新实现分支 `codex/onboard-fastlio2-20261019`。地图、目标、0.4m/s及所有保护保留。
>
> 60秒板端隔离回放597帧、处理延迟P95 88ms、最大106ms；15:26静止初始化和15:30原地图重定位通过，属于重启前历史证据。约15:45重启后旧PID/健康状态失效；16:30获得新静止确认，初始化被另一个SSH会话16:05启动的原厂 `xt16_driver` / `unitree_slam` 独占检查阻止。未绕过保护，不能称当前导航就绪。继续前先确认外部进程所有权与现场位置，再初始化、重定位及无运动验证。
>
> 详见 `board/FAST-LIO2切换与验证_20261019.md`；备份 `board/backups/fastlio2-switch-20261019-151148/`，证据 `board/evidence/fastlio2-20261019/`。最近5.07GB录包已按用户授权转存Mac、SHA一致后删除板端对应副本。运动仍等待明确指令。

> **2026-10-19 14:20 实时状态写盘优化已部署，无真实运动**
>
> `input/runtime/lifecycle/localization` 健康状态改为按导航会话写入 tmpfs，原路径以链接保留；5秒异步归档，内存缺失不使用旧归档放行。用户同意正常结束本次录包，22.9GB文件封包成功且索引完整；融合会话 `board-20261019-133115-18379` 与算法 PID 18562 未重启。导航已重载为 `live-20261019-141719-30947`，参数字节与15项保留文件SHA一致。
>
> 193项Python回归和JS检查通过；归档阻塞注入2000次发布最大1.41ms。停录包旧进程120秒1148样本已无超龄；修复后120秒1146样本点云最大0.418秒、位姿0.319秒，输入未就绪/运行降级/超过0.6秒均0，不能把改善全部归因于代码。当前没有有效保存地图定位，不能把输入健康当成完整导航可执行。系统盘约剩6.7GiB，ext4旧错误226次未修复，保存地图ICP与实机到点仍待验收。
>
> 详见 `board/实时状态写盘优化与测试_20261019.md`、`board/evidence/ram-status-20261019-141430/`、备份 `board/backups/ram-status-20261019-141353/`，最新校验用 `board/ram-status-20261019-deployed.sha256`。


> **2026-10-19 约14:00 性能诊断：先处理实时状态落盘阻塞**
>
> 只读采样已复现点云源年龄1.095秒、导航降级。inputs.py内核栈多次停在ext4文件替换/写回路径，ROS发布与JSON状态写入共用线程；持续录包约9.2MB/s，整理报告时系统盘仅剩约14.1GiB。ext4另有启动时的位图校验错误记录，未执行在线修复或删除数据。保存地图约85.7万点，每轮定位ICP中位约1.17秒；故障会话LIO雷达ICP末段P95约225ms。当前8核总体CPU中位约36%，不能简单认定为算力耗尽。
>
> 详见 `board/板载性能瓶颈诊断_20261019.md` 和 `board/evidence/performance-20261019-135136/`。本轮未重启、未改阈值或算法、未运动。建议先隔离实时状态与大文件落盘、安排录包归档及离线文件系统检查，再做两层ICP优化。现有地图、目标、0.4m/s和0.6秒策略均保留。最新文档用 `board/performance-20261019-documents.sha256` 核对，此前文档SHA为历史版本。


> **2026-10-19 后续策略更新：源年龄上限 0.6 秒**
>
> 按用户明确要求，当前 corridor04（0.4m/s）档的源位姿/点云年龄上限从 0.5 秒改为 0.6 秒，统一用于预演、执行、到点动作、重复性测量及网页判断。baseline 保持 0.5 秒，hall08 保持 0.3 秒。未修改接收年龄、指令有效期、看门狗、融合算法、速度或碰撞保护，未重启服务，未发运动指令。网页需刷新。详见 `board/融合源年龄上限调整_20261019.md`；备份 `board/backups/source-age06-20261019-132723/`；最新核验清单 `board/source-age06-20261019-deployed.sha256`。此前记录的 0.5 秒数据与校验清单为当时历史值。


> **2026-10-19 Mac 接手增补（本轮未发送真实运动指令）**
>
> 已按现场静止确认启动融合，当前融合为 `board-20261019-120109-4452`，导航为 `live-20261019-120958-7350`；后续仍须重新核对进程身份和文件更新时间。旧地图自动重定位未通过，`demo/state.json` 为 `recovery_failed`，不能视为导航就绪。地图、目标和路线已保留，等待现场位置/朝向确认；没有开始或续跑历史任务。
>
> 终点控制增量修复已部署并确认 active_params：GoalAngle/PathAngle 的位置切换距离由 0.12m 同步改为 0.07m，Humble 参数改用 `forward_preference=true`；保留 0.4m/s、8cm/0.12rad、非状态锁存、20秒/5cm进展检查及全部保护。板端真实 MPPI 优化器隔离仿真最终 24/24 通过，原参数同组 15/24；这是仿真，不是实机低速标定或动态验收。
>
> 静止180秒3507样本中位姿源年龄最大0.334秒、点云0.432秒，无超过0.5秒样本；完整定位共载和长期移动仍未验证。观察器复合 unhealthy 计数包含未就绪定位，不应误读为传感器失效。
>
> 详见 `board/终点控制修复与接手记录_20261019.md`；证据 `board/evidence/arrival-fix-20261019/`，有效延迟窗口 `board/evidence/接手-20261019-1205/`；备份 `board/backups/arrival-20261019-1201/`。`source-manifest.json` 已记录本轮增量，下面第9节的旧SHA是历史值；本轮用 `board/arrival-20261019-deployed.sha256` 核对。原生IMU未改，实际进程仍使用 build1/mapping 中的程序。


更新时间：2026-10-19，Asia/Shanghai。本文是工程状态和操作记录，不代表后续实机运动已获现场许可。接手时先只读核对当前状态；历史运行目录和成功结果不能作为当前就绪状态。

## 1. 交接目标与当前结论

- 用户后续用 Mac 网线连接 Go2W，算法继续全部在机器人板载运行；Mac 负责网页显示、SSH和开发。
- 已实现 FAST-LIVO2 融合建图、保存地图重定位、Nav2＋MPPI规划控制、受保护 SportClient 运控、网页二维/三维/RGB相机、目标、多点逐点停靠和中断后显式续跑。
- 2026-10-18晚板端路线 `4 → 1` 最终完成，中间恢复过一次。当前主要遗留问题是接近终点时微小速度无法产生有效运动，触发无进展停车；不能把所有中断都判作传感器掉包。
- IMU时钟漂移、ICP阻塞和实时相机双重限频已修复并部署，有静止共载及预演证据；不等于长期移动测试已全部通过。
- 普通越障模式已在本机原地校验；自动连续上/下楼梯没有实现和验收。楼梯入口到点切模式后结束自动任务，由人工接管；平台上核对定位后另起平地任务。
- 优先保留目前能用的0.4m/s配置和地图，先优化稳定性与末端到位；不要直接切0.8m/s或放宽保护掩盖问题。

## 2. 本次板端在线快照：与历史记录分开

2026-10-19约11:32重新连接后只读检查：

| 项目 | 本次实际结果 |
| --- | --- |
| 主机 | Ubuntu20.04.5、aarch64、Jetson内核5.10.104-tegra |
| 应用目录 | `onboard/current` 指向 `onboard/deploy-20261015` |
| 功耗 | root读取 `nvpmodel -q` 为 MAXN、模式0 |
| 网页 | `go2w-web.service` active |
| 容器 | 只有只读网页容器 `go2w-web-view` 运行；未见运行中的导航容器 |
| 融合 | 历史PID/birth不匹配，未在运行；不能仅看旧 `runtime.json` 的 running 字段 |
| 历史状态文件 | `updated` 已过期约12.5小时；旧 ready=true 不能用于操作许可 |
| 运动标记 | 历史导航目录无 `motion_active`、无 `route_active.json` |
| 地图/任务 | 保存地图仍在；历史路线 completed 2/2，不是待继续任务 |

完整精简快照：`board/evidence/handoff-20261019/runtime-snapshot.json`。本次只写交接和使用文档，未启动融合、重定位、导航或运动。下一次若需要恢复服务，先由现场确认机器人正常站立、保持静止，再通过现有入口初始化，恢复旧地图定位并重新预演。

## 3. 必须分清的目录和运行边界

以下均为**机器人上的路径**：

| 作用 | 路径/入口 |
| --- | --- |
| 稳定应用入口 | `/home/unitree/fast_livo2_port/onboard/current` |
| 当前实际应用 | `/home/unitree/fast_livo2_port/onboard/deploy-20261015` |
| 设备绑定配置 | `board/deployment.json`，包含 backend、fusion_release、sensor_base；不要盲目重建 |
| 原生融合工作区 | `/home/unitree/fast_livo2_port/onboard-iterations/vio-index-20261018`，以设备配置为准 |
| 实际融合主程序 | 上述目录的 `ws/devel/lib/fast_livo/fastlivo_mapping` |
| 传感器基础目录 | `/home/unitree/fast_livo2_port/build1` |
| 实际原生IMU程序 | `/home/unitree/fast_livo2_port/build1/mapping/imu_forward_native` |
| IMU源码和时钟头文件 | 同目录 `imu_forward_native.cpp`、`tick_clock.h` |
| 设备标定 | 应用目录 `board/calibration/livo.yaml`、`camera.yaml`；融合release也有其配置 |
| 地图/目标/固定定位点 | 应用目录 `navigation/mppi/maps/<map_id>/` |
| 地图回收站 | `navigation/mppi/maps-trash/`，不要自行永久清理 |
| 融合最新指针 | `board/current.json`，其folder内有运行日志和健康状态 |
| 导航最新指针 | `navigation/mppi/current.json`，其folder内有状态、参数和执行结果 |
| 交互状态 | `demo/state.json`、`navigation/mppi/selection.json` |
| 网页服务/缓存/访问码 | `go2w-web.service`、`board/web-state/`；不要把访问码上传Git |
| 导航容器 | `go2w-nav2-mppi`，镜像 `go2w-nav2-mppi:humble`，ARM64 |
| 网页只读桥 | `go2w-web-view`，复用同一Humble镜像 |

关键区别：应用源码包默认不包含 `mapping/`。IMU runner 从自身目录执行 `imu_forward_native`，所以仅替换 `onboard/current` 的Python应用不等于替换了实际IMU。修改原生IMU需核对、备份并部署到 `sensor_base/mapping` 的源码、头文件和重编译产物，再确认实际二进制SHA和进程路径。

当前绑定：MAXN、CPU后端、4线程、5Hz视觉、filter4/surf0.15。MAXN不是固定锁频，也不代表FAST-LIVO2已GPU化。原生融合运行ROS1 Noetic，master为回环11331；IMU源使用ROS2 Foxy控制域0；Nav2在Humble容器的隔离域79。不要把不同ROS发行版环境混在一个维护shell中，也不要把导航DDS直接接入机器人运控域。

## 4. Mac 接入和首次读取

Mac使用可识别的千兆以太网适配器连接原板端网口，设置未占用地址，例如 `192.168.123.99`、掩码 `255.255.255.0`，直连网关/DNS不填。Wi-Fi可以保留上网，机器人网段需绕过VPN/代理，避免同网段冲突。

网页固定使用 **http://192.168.123.18:8088/**；当前Host白名单不接受任意域名/其他IP，未启用HTTPS。必要时允许浏览器访问本地网络。新版Safari/Chrome为预期客户端，本轮尚未完成用户Mac实测。

Mac终端先读取此文件：

```bash
ssh unitree@192.168.123.18 'cat /home/unitree/fast_livo2_port/onboard/current/board/CODEX_HANDOFF_20261019.md'
```

首次SSH核对主机身份；交互输入密码，不在脚本、命令参数、Git或交接文档里保存密码。SSH若出现机器人ROS环境选择提示，可先完成选择；实际维护命令使用现有入口的干净环境。

访问码查看、网页服务状态：

```bash
ssh -t unitree@192.168.123.18 'bash /home/unitree/fast_livo2_port/onboard/current/网页控制台.sh key'
ssh -t unitree@192.168.123.18 'bash /home/unitree/fast_livo2_port/onboard/current/网页控制台.sh status'
```

访问码与SSH密码不同。Mac不必安装ROS、RViz、Docker或机器人SDK；旧 `板载可视化.sh` 的本地RViz入口依赖Ubuntu。网页使用Mac绘图，计算在板端。保持主操作页前台、不合盖休眠：发起运动的登录会话超过5秒未续约会请求停车，新电脑登录不会自动接替原会话。

## 5. 接手后的只读检查与维护入口

在机器人应用目录执行。部分状态文件由root创建，读取时可能需要sudo，不能因权限错误而删除/重新创建状态文件。

```bash
cd /home/unitree/fast_livo2_port/onboard/current
readlink -f .
cat board/deployment.json
bash 板载运行.sh fusion-status
bash 板载运行.sh nav-status
bash 网页控制台.sh status
```

需要root时，脚本会提示sudo。其余可单独用 `sudo /usr/sbin/nvpmodel -q`、`sudo docker ps`、`sudo journalctl -u go2w-web.service -n 80 --no-pager` 检查。不要把Docker权限变化或全系统升级当成接手前置条件。

获取 `current.json` 指向目录后检查：

- 融合：`runtime.json`、`health.json`、`image_health.json`、`bridge/imu_health.json`、`supervisor.log`、各传感器/融合日志；同时确认PID与birth。
- 导航：`runtime.json`、`input.json`、`localization.json`、`lifecycle.json`、`active_params.yaml`、`motion_profile.json`。
- 任务：`route_progress.json`、`last-action-result.json`、`protected-execute-*.json`、`motion-commands*.jsonl`、`controller_server.log`、`bt_navigator.log`。
- 优先读取触发当时的 `failure_health_snapshot` 和具体失败原因；停车后恢复的新状态不能替代故障现场。

健康服务运行时，可只读采样：

```bash
sudo /usr/bin/python3 board/observe_latency.py --seconds 180 --output board/evidence/接手日期-本轮新目录
```

它不新开SDK/雷达端口、不发送运控。只读取旧的过期文件不构成连续数据验证；确认文件持续更新。脚本中的 `motion_marker_observed` 可能来自预演冻结地图修正，必须结合执行结果中的 `execute` 判断是否真实运动。

需要启停时使用已有入口，不跳过互斥或直接杀全局进程：

| 命令（在应用目录） | 效果/使用条件 |
| --- | --- |
| `bash 板载运行.sh fusion-start` | 初始化传感器和融合；必须现场静止；不启动自主运动 |
| `bash 板载运行.sh nav-start` | 启动规划/定位接入服务；不启动自主运动 |
| `bash 板载运行.sh stop` | 取消当前运动/路线任务，现场核对停稳 |
| `bash 板载运行.sh nav-stop` | 停导航服务；先正常停止任务 |
| `bash 板载运行.sh fusion-stop` | 停融合；必须先停止导航任务 |
| `bash 板载运行.sh shutdown` | 按入口顺序停止本项目任务、导航、显示和融合 |
| `bash 网页控制台.sh start` | 仅启动网页后台和被动显示 |

不要用 `pkill -f python`、删除锁文件/运动标记、重复开传感器客户端或强杀封包中的rosbag来解决冲突。融合由独立 `go2w-fusion-board-*.service` 管理，网页重启不应杀掉融合；网页服务重启会请求停止网页发起的任务。

## 6. 正常业务流程与保护条件

新图：静止初始化 → 确认就绪 → 遥控扫图 → 停稳保存 → 地图定位验证 → 记录/地图添加点 → 保存路线 → 预演 → 确认执行。结束扫图后保留融合用于定位，导航静态底图不继续累计。

旧图：加载地图 → 保持静止 → 自动/地图位置朝向提示/已标记固定点恢复 → 核对机头箭头 → 新预演 → 确认执行。看到旧图不等于定位成功；固定点仅作匹配初值，不能强行赋坐标。

多点逐点停稳，默认停留2秒再下一点。坐标/朝向/模式动作变更、地图或融合会话变化均使旧预演失效。预演60秒有效，预演后移动超过5cm或约5.7°需要重预演。

停车后同会话、同地图、同路线与目标未改变时，用“预演剩余路线 → 继续未完成任务”。从第一个未确认完成点重新规划；数据恢复不会自动运动。重启融合/重新建图后不能续用旧会话进度。当前历史任务已经全部完成，不要把旧任务重新当作未完成续跑。

当前平地档 `corridor04`：vx上限0.4m/s，反向下限−0.1m/s，角速度上限0.8rad/s；实际运行以 `motion_profile.json`、`active_params.yaml` 和网页“运行中”值为准。`hall08`保留在代码中，本轮未动态验收。配置文件生成后，运行中的参数不会因更改源文件自动更新。

需要保留的主要检查：地图/会话绑定、定位健康、源时间和接收时间、位姿跳变、轨迹扫掠碰撞、指令有效期、SDK看门狗、模式反馈、停车及停稳验收。0.4档源位姿/点云年龄上限0.6秒，0.8档0.3秒（baseline档仍0.5秒）；执行订阅回调接收年龄另有0.4秒odom/0.8秒局部代价图要求。不要只放大某个超时来掩盖数据阻塞。

机身包含轮足外缘75×44×59cm；用户选择机身外额外约10cm余量。碰撞检查与Nav2 footprint需一致，不将 inflation_radius=0.1 当作10cm机身余量。连续楼梯不纳入当前二维自主路径。

## 7. 已部署修复与证据索引

### A. 视觉地图增长/检索（10月18日）

修复负坐标体素索引不一致、相机背后点写入和雷达平面查询尺度问题，加入视觉点/检索耗时指标。应用 `board/visual_index.patch`，原生工作区为当前 `fusion_release`。300秒同录包A/B：视觉新增点139315→412、末100帧检索中位数24.816→5.668ms，RSS峰值661.3→296.9MiB；轨迹差异是算法间一致性，不是真值。另有530秒移动录包回放。

说明/证据：`board/测试前审阅_20261018.md`、`board/evidence/vio-fix-20261018/`。原87分钟录包中途损坏，仅恢复前930秒；不可称已完成87分钟修复验证。

### B. IMU时钟、ICP并发、相机限频（10月18日晚）

1. 原生IMU只在启动对齐tick，约两小时累计约0.2秒偏差。`mapping/tick_clock.h` 改为60秒滑动窗口稳健频率估计，限制频差/相位校正，保留时间连续；真实接收延迟仍保留，时钟复位/跳变拒绝。实际程序已另行部署到 `build1/mapping`。
2. `navigation/mppi/localization.py` 将ICP移到单独进程，最多一个待处理任务；ROS接收/TF和状态更新不再被ICP阻塞。匹配门槛保持，过期结果不能激活定位，运动中不改地图变换。
3. 实时SDK采集已5Hz，解码端再次5Hz限频误丢边界抖动的新帧。`board/image_sampling.py` 与 `replay_decode.py --source-rate-limited` 在实时路径取消第二次限频；离线10→5Hz仍抽帧，保留原始时间戳。
4. `health_policy.ContextError`、`execute.py` 保存故障现场；`observe_latency.py` 只读采样；新会话激活清理旧预演凭据。

验证：392万条实测IMU回放最大超前由约0.2秒降至1.51ms；±80ppm等四组两小时模拟稳态误差低于0.24ms。最终180秒3503样本无健康失败，点云年龄最大0.430931秒、位姿最大0.355362秒；3轮 `execute=false` 预演通过。此为静止最终验证，不能延伸为所有移动/长时间场景保证。

说明：`board/传感器超时修复记录_20261018.txt`。证据：`board/evidence/clock-icp-20261018/final180/{summary.json,previews.json}`，以及同级 `image-gaps.json`、`tick-clock-replay.json`。`static120` 和 `preview40` 是图像修复前对照，其中仍有0.542秒超时，不能当最终通过证据。

备份：`board/backups/clock-icp-20261018/`、`board/backups/vio-index-20261018/`。回退需要先正常停任务、导航和融合；应用与实际原生IMU要对应恢复，重新初始化/重定位后重预演。

## 8. 当前首要未解决问题：终点附近无进展

证据目录 `board/evidence/arrival-stall-20261018-2248/`，先读 `说明.txt`、`summary.json` 和三个 `protected-execute` 结果。

- 22:48首次到点4最终误差8.56cm，超出8cm标准；朝向误差2.26°已经合格。
- 机身坐标残差约后方3.47cm、右侧7.83cm，主要是横向误差。
- 最后17秒vx中位数−0.0177m/s、wz中位数−0.0271rad/s，融合位置净变化只有2.7mm，触发20秒无进展（`Failed to make progress`）。SDK停车返回0，停稳校验通过。
- 同100秒移动窗口499次位姿，源时间最大间隔0.217秒、接收最大间隔0.327秒，接收时最大年龄0.262秒。本次停车由进展检查触发，没有证据说明是传感器超时。
- 显式续跑后点4成功，再到点1成功；最终融合估计4.40cm、1.17°，route completed 2/2，resumes=1。此误差尚非卷尺真值。

代码入口：`navigation/mppi/make_config.py` 生成控制配置，基础 `params.yaml`、`speed_profiles.py`；`execute.py` 消费平滑速度并进行健康/碰撞检查，经 `guard_server.py`、`guard_client.py`、`guard/relay.py`、`sport_guard.cpp` 调用SDK。`run_protected.py`、`arrival_runner.py` 管理到点动作。

控制器为MPPI DiffDrive，vy=0，不支持直接侧移。SimpleGoalChecker xy=0.08m、yaw=0.12rad、stateful=false；SimpleProgressChecker要求20秒内移动0.05m。`VelocityDeadbandCritic` 的0.08是软代价，不能保证输出速度超过0.08；平滑器 `OPEN_LOOP` 仅指平滑速度估计，整体导航仍用实时融合位姿闭环。`arrival_check.py` 负责停车后验收，不会自动再调整位置。

下一步应审阅接近目标时位置和最终朝向的协调，以及有效低速响应与预测模型的一致性。转向带来的平移需被闭环追踪。不要仅硬夹最小速度、延长无进展时间或放宽8cm容差；这会影响碰撞预测和到点质量。

建议在独立改动中对照：纵向误差、横向误差、朝向误差三类起始情况，每类至少3轮；用同一机身固定参考点和地面朝向线量实误差，保留命令、融合位姿、故障现场和结果。先离线/无运动预演，真实移动前由现场明确确认路线与监控。

长距离另外未验收：初始建图全局栅格60×60m边界、导航地图采样上限和长时间资源增长、重复结构走廊重定位、平台高度变化、上下楼梯落差与三维路径。地图看起来足够大不等于上述能力已具备。

## 9. 开发、Git、部署和最小检查

上一个开发电脑目录为 `/home/river/文档/ChatGPT/巡检/fast_livo2_port`，并不是Mac的路径。Git远端 `git@github.com:justic123/go2w-fastlivo2-nav.git`，本机分支 `codex/onboard-gpu-iteration`，本地HEAD `2e1abeade793cd6795bbe62d4cf301580395d829`。目前有大量已修改/未跟踪源码；**HEAD或远端不代表当前全部修复已提交/推送**。

本次核对板端应用目录没有 `.git`，它是部署目录，不要直接在那里 `git pull`、`git reset --hard`，也不要把地图、凭据、录包全量 `git add`。Mac可另建源码工作区并从板端核对必要源码，先比较，再按小范围部署。旧电脑的完整脏工作区应另外保留，板端只含部署所需子集。

`board/stage_deployment.py --code-only` 可生成应用代码包和 `board/source-manifest.json`，会保留设备绑定、标定、地图、网页凭据、速度选择和运行状态；但不包括 `mapping/` 原生改动。顶层文档采用白名单，`Mac网线控制与操作说明.md` 需显式同步；本文件位于board目录，会入包。比较清单SHA与实际文件，不只看Git提交号。改动前备份本轮涉及文件及设备绑定，不覆盖现场地图和任务。

本次（10月19日）离线33项网页后端、105项地图/任务及JS交互检查通过；未做Mac现场实测。可在隔离源码工作区重现：

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s board/web -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=demo:navigation/mppi /usr/bin/python3 -m unittest discover -s demo -p 'test_*.py'
node board/web/test_ui.js
bash -n 板载运行.sh 网页控制台.sh
```

不要求为了接手在板端安装Node；JS测试可在Mac源码工作区进行。Python测试使用numpy/yaml等现有依赖。原生IMU另有 `mapping/test_tick_clock.cpp`、`mapping/test_imu_native_board.py`；后者须在独立ROS master，不在实机传感器master运行。

核对实际文件（当时SHA收录于本次runtime-snapshot）：

```bash
sha256sum /home/unitree/fast_livo2_port/build1/mapping/imu_forward_native
sha256sum /home/unitree/fast_livo2_port/build1/mapping/tick_clock.h
sha256sum board/source-manifest.json
```

IMU二进制当时SHA：`5a1338d898a7c9d6b33c00e15d2f0896a76189f782b3e9a704bd06e3ec521203`。时钟头文件：`6b45ccdd9ee904a36de0f1957d62220672dddd976cefaf53527cf301d05ed053`。应用source-manifest文件：`a5bc31cb42e7713d09353fe7232a934ade76ee3ff6e533d77245a49cb9ba7da2`。本轮仅更新说明文档，不改源码和该历史应用清单；因此清单中旧文档哈希可能与新说明不同。本轮新增/更新的文档另用 `board/handoff-20261019-documents.sha256` 核验。

## 10. 继续阅读与接手顺序

1. 先读本次运行快照，检查当前进程身份和更新时间，必要时请现场保持静止后恢复服务。
2. 阅读 `Mac网线控制与操作说明.md`、`board/web/README.md`、`board/停止后继续任务说明_20261018.md`、`board/固定位置重定位使用说明.md`。
3. 分清传感器真实超时、网页续约丢失、定位不通过、碰撞停车和末端无进展，不统一当“掉包”。
4. 首先保存当前可用参数和地图，针对第8节做有证据的小范围控制优化；随后扩大平地长距离和持续运行验证。
5. 完成新变更后记录实际部署文件/运行配置、测试范围和剩余问题，再更新此交接入口。

本文不要求自动开始运动；沿用网页预演、显式执行和现场接管流程。用户偏好中文沟通、直接完成可验证工作、保留当前能用版本；不要重复从零安装或重新扫图来回避未查明的问题。
