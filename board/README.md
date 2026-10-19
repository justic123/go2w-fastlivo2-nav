> 2026-10-19流程入口：[Mac网线控制与完整操作说明](../Mac网线控制与操作说明.md)、[网页工作台](web/README.md)。当前算法在板端，电脑仅作操作和显示。10月18日晚已有板端多点任务完成记录，仍有末端无进展中断待优化；本轮Mac在线验收尚未进行。下文包含此前各轮实验记录，不应把历史“当前状态”当作实时状态。平地调速和楼梯边界见 [10月18日审阅](测试前审阅_20261018.md)。

# Orin NX 板载迭代

开发分支：`codex/onboard-gpu-iteration`。

## 网页控制台（2026-10-16）

浏览器访问 **http://192.168.123.18:8088/**，在项目目录运行 `bash 网页控制台.sh key` 查看独立访问码。
已提供二维地图/代价图、三维点云、广角相机、路径显示及建图、地图恢复、目标和多点路线操作。
所有算法与网页后台在机器人板载运行，电脑只需浏览器。详细步骤见 [网页使用说明](web/README.md)。
网页开机自动启动，建图和运动不会自动执行。原有终端菜单需退出后再进行网页操作，避免操作锁冲突。

## 当前板载部署入口（2026-10-16）

后续建图、融合定位、旧图匹配、Nav2＋MPPI及受保护高层运控均在Go2W上运行。
电脑仅通过SSH操作菜单、接收画面并运行RViz，关闭RViz不会停止板端定位。
板端系统仍是Ubuntu20.04／JetPack5；FAST-LIVO2原生运行，Humble导航使用ARM64
Ubuntu22.04容器，不把电脑的x86镜像或ROS安装复制到板端。

板端统一目录：`/home/unitree/fast_livo2_port/onboard/current`。
新的入口与旧的`build1`入口互斥，不要同时启动之前的本机建图、楼层导航脚本。

在电脑的本项目目录打开交互菜单：

```bash
bash 板载运行.sh
```

或SSH到Go2W后执行：

```bash
cd /home/unitree/fast_livo2_port/onboard/current
bash 板载运行.sh
```

首次启动按现有sudo提示认证，未保存密码，也未给unitree账户新增Docker管理权限。
菜单1新建图（站立静止，成功后再遥控），菜单2结束采集并保存导航地图；
菜单3记录点，4预演，5显式执行导航；14–16编辑、预演、执行逐点停稳路线。
旧图先选13，再用9自动或10辅助重定位，位置和朝向核对后再预演。
地图和目标已复制至新目录，但旧的融合会话与预演授权不会被恢复。
结束扫图后保持融合运行用于定位，不继续累积导航静态地图。

电脑另开终端显示（需Ubuntu22.04及ROS2 Humble/RViz2）：

```bash
bash 板载可视化.sh mapping      # 彩色点云、图像、轨迹
bash 板载可视化.sh navigation   # 二维障碍膨胀图、路径、机头、途经点
bash 板载可视化.sh cloud        # 导航三维视图
```

显示入口按板端阶段选择`camera_init`或`map`；结束扫图后重新打开导航窗口。
若手动切换，未选定地图的扫图阶段用`camera_init`，保存/恢复旧图后用`map`。
辅助定位在导航窗口点`2D Pose Estimate`并拖出机头朝向。
地图目标点击使用`/demo/goal_pose`，只保存目标；点击本身不会运动。
显示链路仅转发列明的地图/TF/姿态话题及这两种点击输入，禁止转发速度或直接导航命令；
通过SSH回环转发，不将导航DDS加入宇树的控制域。
同一种显示窗口只开一份，退出RViz即关闭对应显示导入进程。

单独启停和检查（以下在板端统一目录执行）：

```bash
bash 板载运行.sh fusion-start  # 仅传感器和融合，需静止初始化
bash 板载运行.sh fusion-status
bash 板载运行.sh nav-start     # 仅规划服务，不运动
bash 板载运行.sh nav-status
bash 板载运行.sh stop          # 取消本项目当前导航
bash 板载运行.sh nav-stop
bash 板载运行.sh fusion-stop
bash 板载运行.sh shutdown      # 按取消导航、停导航、停融合顺序清理
bash 板载运行.sh power
```

不要在运动期间直接停融合或断电。主管不自动重启并清空地图；输入过期会明确报错，
运控看门狗仍保留。录包作为辅助任务，磁盘不足先停录包，不因录包退出重启定位。
日志在`board/runs/`及`navigation/mppi/runs/`，每次会话单独保存。

MAXN已保存为模式0，并将`/etc/nvpmodel.conf`的`PM_CONFIG DEFAULT`设为0，
保留原厂`nvpmodel.service`开机应用；原配置备份在`/var/lib/go2w-deployment/power/`。
只设置功耗自动恢复，导航与运动不会开机自动执行。
未锁定jetson_clocks、未改温控或风扇保护。板端时钟曾为1970年，已在服务停止时校正，
并更新系统自带timesync时钟文件；融合运行期间不要手动跳变系统时间。
2026-10-16已查明开机晚期`/etc/rc.local`中的`hwclock -s`会从默认Tegra RTC读回错误时间，
覆盖timesync恢复的日期。已备份原文件，明确从RTC0恢复UTC并校正RTC；
再次重启算力板后，日期保持2026-10-16，MAXN仍为0、8核在线、CPU上限1.984GHz，
原厂功耗服务退出码0。时钟修改备份在`/var/lib/go2w-deployment/clock/`。
如果以后启动时日期又异常，入口会拒绝创建新地图；应停止传感器后重新校时。

当前复测使用MAXN、OpenMP线程数和上限均为4、BLAS1、640×360视觉5Hz，
点云过滤间隔4、表面降采样0.15m；保留本机验证过的传感器外参，CPU执行估计器。
10Hz候选仍保留，但2026-10-16连续静止运行约12分钟后处理延迟升高到1秒以上，
融合主管按原有规则保护退出，导航也因输入过期退出。温度约61℃、内存仍有约11GB可用，
尚不能把此前60秒或530秒通过视为10Hz长时间稳定。当前未放宽新鲜度或积压保护门限。
`board/deployment.json`中的`image_hz`选择5或10，SDK取图、解码限频和算法配置同时应用，
不支持的值会拒绝启动；该设备文件不随代码更新包覆盖。改档应先正常停止导航和融合，
重新初始化与恢复地图；不能在线改频后沿用旧预演。
2026-10-18板端已选择corridor04：前进上限0.4m/s、角速度上限0.8rad/s；baseline回退档仍为0.2m/s。
此前大厅迁移包的0.8m/s档没有自动应用于板端；该档要求点云/位姿年龄≤0.3秒，
本次板端点云年龄约0.38秒，需先优化输入延迟并做动态验收，不能只改速度上限。
原`build1/ws`及此前实验二进制均保留，部署不意味着已开启CUDA估计。
位于途经点的越障切换接口也已包含；未验证的SDK模式仍会在运动前被拒绝，
默认“不切换”。

已完成板端无运动验证：ARM64导航镜像构建、完整Nav2生命周期、MPPI候选控制约20Hz、
静止新建图/保存/固定地图定位/记录点/受保护预演，以及二维膨胀图/TF/箭头传到电脑。
一次60秒静止共载记录为融合9.95Hz、处理延迟p95约0.243秒、位姿年龄p95约0.231秒、
点云年龄p95约0.380秒、CPU最高61.1℃、最低可用内存约12GB。
小范围静止地图的资源占用不能代替整楼层动态测试。
依赖解包期间曾因持续积压超过1秒触发退出；保留故障日志，没有放宽导航新鲜度门限。
初始化先收到计时、尚无位姿的竞争条件已修复，必须连续稳定4秒且有新里程计样本才报就绪。

辅助重定位已修复候选选择顺序：先筛选质量与提示修正范围，再查找两两一致的候选组，
最后选组内代表。此前5次ICP中有4次一致时，一个匹配率更高但偏离的结果仍可能导致整体
误判为不一致。现在辅助定位仍要求至少4次一致（全局定位至少3次），每个支持结果均须
匹配率>0.65、RMSE<0.12m、倾斜<0.25rad；相对提示平移<0.75m、旋转<0.35rad。
组内任意两项平移差<0.15m、旋转矩阵差的Frobenius范数<0.1；不会通过链式相邻凑数。
原有提示180秒、采集30秒、结果60秒的有效期、静止检查和独立实时地图验证均保留。
回归用旧数据重新选择只能作离线证明，实际恢复必须重新采集并通过实时定位验证。

2026-10-16使用新点选和新采集成功恢复`demo-20260930-003458`：辅助匹配4个候选一致，
随后独立实时匹配约0.90–0.95；4个原目标点重新绑定到本次融合会话，旧预演失效。
用户已现场确认重新打开的二维RViz可交互，位置和朝向基本正确。
5Hz融合＋旧图定位＋完整Nav2＋显示60秒检查通过：融合输出4.97Hz，处理延迟p95
0.226秒、最大0.234秒；导航位姿年龄p95 0.329秒，点云年龄p95 0.382秒、最大0.442秒，
CPU最高62.7℃、最低可用内存约12.35GiB。
对原目标点3的无运控连接测试获得42个路径点，8秒内160个MPPI候选指令、约20Hz，
取消后归零；没有启动SDK运动桥，没有实际运动。完整楼层动态导航仍待现场验收。

显示桥已修复“60秒没有用户点击就断开”的错误：等待输入先检查可读状态，无点击不会
结束持续输出的连接，阻塞发送或不完整数据包仍会触发重连。
本轮旧RViz窗口曾不响应正常退出，已仅重启电脑显示进程并清理其缓存，板端融合与定位
未重启。显示断流的修复不等于已经证明该次GUI无响应的全部原因；后续仍需观察。

下面是此前性能实验的方法和结果，不能把离线通过等同于长距离运动已验收。

第一阶段是 **CPU定位 + CUDA对照计算**。CUDA输出不会进入位姿、协方差或地图更新；
没有 `gpu` 实机执行模式。先测量完整负载与观测累加的收益，再决定是否扩大GPU范围。
本目录的离线构建和回放工具不调用驱动、SDK、导航、功耗切换或运动命令。
`live_probe.py` 是独立的静止实测入口：它会启动既有雷达驱动、只读取图的相机客户端和
IMU订阅桥，不启动导航或运动控制，须在现场确认静止后使用。

## 本阶段实现

- `fast_livo2.patch` 基于已恢复的 `upstream/FAST-LIVO2`：增加完整LIO/VIO处理计时、主循环工作计时、同步/回调/IMU计时，以及内部队列数量、最旧数据年龄、地图体素数量。
- 原有状态测量时间戳用于里程计，不用发布时间伪装低延迟；板端既有的该项修复也保留。
- `GO2W_PROFILE=1` 发布 `/go2w_lio/profile`，没有订阅者时不额外保存原始数据。
- `GO2W_CUDA_BACKEND=cpu` 默认只使用CPU；`shadow` 对同一批LIO观测执行FP64的 `HᵀWH` 与 `HᵀWr` 累加，比较结果后继续使用CPU结果。
- GPU固定归约树，不使用浮点原子累加，不启用CUDA fast-math，不降低FP64精度；误差条件为每元素 `abs(error) <= 1e-8 + 1e-10*abs(cpu)`。这是本模块诊断门限，不是定位精度保证。
- 不一致、CUDA错误、非法后端名称、超过200万观测均显式失败，不静默截断或切换后端。现有采集主管仍会将算法退出视为故障。
- 支持CPU构建：`GO2W_WITH_CUDA=OFF`。CUDA11.4构建使用 `sm_87`，不要求升级JetPack。

计时有嵌套关系：`loop_work` 包括 `estimation_and_outputs`，后者包括 `lio_full` 或 `vio_full`，
不能把所有字段相加。`loop_work` 累计两次有效更新之间的工作，排除主动等待和诊断发布本身；
`lio_cuda_total` 包含首次初始化、分配、复制、kernel与同步，而非只有GPU kernel时间。
源时钟下的 `processing_lag_s` 与观察器单调时钟分别保存。队列观测只覆盖算法内部缓存，
不等于ROS传输层的完整队列观测。此阶段未修改队列容量、数据丢弃规则或导航保护。

## 准备与构建

先使用项目的 `dependencies/restore.py` 恢复固定依赖。准备脚本核对原提交号和已有补丁摘要，
拒绝覆盖目标目录或在来源有额外修改时继续。

```bash
python3 board/prepare.py --output /absolute/staging/FAST-LIVO2
```

在板端创建全新的 release 目录，将准备结果放在 `release/ws/src/FAST-LIVO2`，
将本目录工具、`desktop/decode_jpeg.py` 放在 `release/tools/`，并复制该机器当前验证过的
算法及相机配置至 `release/livo.yaml`、`release/camera.yaml`。不要复制参考仓库的外参。

```bash
bash release/tools/build.sh /absolute/release
```

构建使用板端既有的 Noetic、PCL、OpenCV、Sophus，复制 vikit/cv_bridge 源码到独立工作区，
不覆盖 `build1/ws` 的原二进制、源码或日志。原版仍是默认实机入口。
新二进制实际被使用的路径与源码SHA-256记录在部署证据中；只切换Git分支不会切换实机二进制。

## 验证

`cuda/check_normal_equations.cpp` 覆盖空输入、跨线程块尺寸、不同尺度、增长/缩小缓存、
FP64对照、重复输出与容量拒绝。额外使用Compute Sanitizer需板端允许访问GPU调试接口。
工具权限错误必须作为未完成检查记录，不能当作内存检查通过。

先停止本项目采集与导航，再运行无运动回放：

```bash
python3 release/tools/replay.py --release /absolute/release \
  --bag /absolute/existing/sensors.bag --seconds 120 \
  --backend cpu --output /absolute/new-run/cpu
python3 release/tools/replay.py --release /absolute/release \
  --bag /absolute/existing/sensors.bag --seconds 120 \
  --backend shadow --output /absolute/new-run/shadow
python3 board/analyze.py /absolute/new-run/cpu /absolute/new-run/shadow
```

回放默认独立ROS1端口11441，只播放点云、IMU、JPEG，防止录包中的旧里程计混入。
每次输出目录必须是新的。脚本检查采集/融合冲突并只回收自己创建的进程组。
诊断、位姿和过程错误均保存；原始录包不变，真实地图/目标点/路线不参与回放。

### CPU与输入负载对照

把 `replay.py`、`replay_decode.py`、`analyze.py`、`performance_matrix.py` 放在同一工具目录。
以下命令对同一录包依次测试5Hz视觉、纯LIO和10Hz视觉配合点云降采样：

```bash
python3 tools/performance_matrix.py --release /absolute/release \
  --bag /absolute/sensors.bag --output /absolute/new-comparison \
  --seconds 120 --cases dense5 lio_dense balanced10
```

`dense` 使用release现有点云配置；`balanced` 仅在本轮独立ROS参数中覆盖
`preprocess/point_filter_num=4`、`preprocess/filter_size_surf=0.15`，不改变标定或正式配置。
`replay.py --image-profile off` 运行FAST-LIVO2自身的LIO模式，不是独立FAST-LIO2。
`--threads 1/2/4` 控制OpenMP线程上限，不代表所有阶段都能并行。

5Hz回放按原始图像时间戳抽帧并记录实际发布频率；仅设置旧解码器的
`GO2W_IMAGE_PROFILE=5hz` 不会把10Hz录包变成5Hz。10Hz模式保留输入频率，
不会补帧或修改时间戳。不能只凭进程退出码或最后一次缓存的profile年龄判断实时通过；
还须核对运行期间延迟、最后雷达覆盖范围与最后可融合图像，见下文录包尾部审计。
完整报告保存在每轮的 `summary.json`、`parameters.yaml`、`comparison.json` 和
`*-tegrastats.log` 中。阶段计时存在嵌套，禁止直接相加。

### 静止实时输入验证

在现场保持静止、其他采集及回放均已结束时，可做一次有明确结束时间的实测：

```bash
python3 tools/live_probe.py --release /absolute/release \
  --output /absolute/new-live-probe --seconds 90 --image-profile 10hz \
  --point-filter-num 4 --surface-leaf-size 0.15
```

该入口使用独立ROS1端口11641，记录测量年龄、融合诊断、原始输入链路健康和温度，
结束时回收自己的进程组。它不会创建正式地图会话、修改目标点或发送运动指令。
静止实测通过不能代替带Nav2/MPPI的移动、整层及长时间验收；降采样后的定位精度需另测。

### 2026-10-15 板载性能对照结果

设备为Orin NX 16GB，L4T35.3.1，15W模式，4核在线，CPU上限1.6512GHz。
使用独立诊断版本 `onboard-iterations/20260930-cuda-shadow-01` 的CPU后端，
输入为 `build1/livo-manual-20261014-104646-14281/sensors.bag`。
以下延迟均为原始测量时刻到源回放时钟的年龄，不是跨电脑网络延迟或相机曝光延迟。

| 配置 | 回放输入时长 | 延迟P95 | 最大延迟 | 结果 |
|---|---:|---:|---:|---|
| 原密度，10Hz视觉 | 90秒 | 6.60秒 | 7.78秒 | 积压 |
| 原密度，纯LIO | 90秒 | 2.59秒 | 3.26秒 | 仍有积压；这是FAST-LIVO2的LIO模式 |
| 原密度，5Hz视觉 | 90秒 | 0.37秒 | 0.54秒 | 短片段跟得上输入 |
| filter=4、leaf=0.15m，10Hz视觉 | 90秒 | 0.23秒 | 0.44秒 | 短测通过 |
| filter=4、leaf=0.15m，10Hz视觉 | 530秒 | 11.50秒 | 16.95秒 | 长测失败；运行期间持续积压 |
| filter=4、leaf=0.15m，5Hz视觉 | 530秒 | 0.26秒 | 0.46秒 | 本轮离线性能通过，位姿约5Hz |

5Hz长测实际解码频率约5.000Hz，完整保留雷达和IMU输入；融合调度随图像降为约5Hz。
算法RSS最高约3.42GiB，CPU最高约54.7℃。原有10Hz精细配置的主要压力出现在
点云匹配和地图扩大后的视觉更新，不能用单次平均耗时或静止短测替代持续回放。
诊断中的CPU观测矩阵累加平均仅约0.30ms，既有CUDA shadow模块不覆盖主要耗时。

另做了90秒真实传感器静止验证，使用10Hz降采样候选：正常采集窗口排除最初10秒与
输入结束后阶段，处理延迟P95约0.24秒、最大约0.25秒，图像约9.99Hz，输入桥无丢云、
无过期丢云、无缺IMU、无非有限位姿。启动阶段曾出现约1.45秒积压，记录保留在完整统计中；
后续静止测试入口已要求连续4秒数据新鲜且位置稳定后才报告ready。
随后完成5Hz候选60秒真实传感器静止复测：连续4秒稳定门槛通过，融合输出约4.998Hz，
整个融合诊断窗口延迟P95约0.214秒、最大约0.483秒；正常采集窗口排除最初10秒及
输入结束后阶段，延迟P95约0.170秒、最大约0.173秒。主管在停止输入后的末尾采样
仍包含最高约2.02秒的测量年龄，不能将它混同于正常采集时的处理延迟，也不能删除
完整统计。585帧雷达全部发布，无队列丢云、过期丢云、缺IMU或非有限位姿，
CPU最高约55.1℃。静止位置跨度约3.9/1.9/1.0mm（XYZ），不是绝对定位精度。
实验进程均已回收，功耗仍为15W；尚未进行板载Nav2联调或移动精度验收。

长测5Hz与10Hz在相同时间戳的水平轨迹差异P95约1.17cm、最大约3.85cm，
高度差异P95约23cm、最大约34cm。两条估计轨迹都不是真值，不能据此宣称定位误差为1cm；
后续需测量实际到点误差，并核对高度、地面和障碍过滤，才能用于导航验收。

候选参数见 `profiles/balanced5.json`。板端独立候选目录为：
`/home/unitree/fast_livo2_port/onboard-iterations/performance-20261015-01/candidate-balanced5`。
该目录保留既有标定，并引用原诊断版本的工作空间；它是独立测试配置。
原始日志、运行参数、二进制来源、统计和图表保存在 `board/evidence/performance-20261015-01/`，
其中 `performance_summary.json` 为汇总，`performance_comparison.png` 为延迟曲线。

CPU与shadow的完整链路耗时只能用于判断新增开销，不能报告成“GPU加速比”，
因为shadow会同时计算两种结果。矩阵模块的CPU/GPU总耗时差异也不能代替整机收益。
发布GPU定位前仍需独立精度评估、故障处理验证与长时积压试验。

### 功耗模式与后续对照

2026-10-15读取这台机器的 `/etc/nvpmodel.conf` 和sysfs，实际配置如下。
上述基线成绩均来自15W。随后按现场授权切换至MAXN并重启算力扩展坞，
下表列出读取的模式资源；没有应用 `jetson_clocks` 锁频。

| 模式 | nvpmodel ID | 在线CPU核数 | CPU频率上限 |
|---|---:|---:|---:|
| 15W（基线） | 2 | 4 | 1.6512GHz |
| 25W | 3 | 8 | 1.4976GHz |
| MAXN（当前） | 0 | 8 | 约1.984GHz，仍受硬件与热管理约束 |

25W增加可并行使用的核数，但降低单核频率上限；对以CPU点云匹配、视觉更新为主的
FAST-LIVO2，不能据功耗数字直接判断速度。MAXN相对当前的频率上限增加约20%，
这不是算法加速比。线程扩展、调度和额外传感器/规划进程是否获益须实测。

本轮保留15W/5Hz候选作为回退，先对照MAXN下的2线程和4线程，每轮固定二进制、
标定、530秒录包及图像配置；记录延迟P95/最大值、持续积压、温度、实际CPU频率与
模块输入功率。25W尚未实测，不能据模式名称推算它的表现。
短时静止通过不能代替移动长测，也不能据此直接增加导航速度。

切换前GPU `tpc_pg_mask=252`，25W/MAXN配置要求240；重启后已读取到240。
[NVIDIA功耗控制说明](https://docs.nvidia.com/jetson/archives/r35.3.1/DeveloperGuide/text/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html#power-mode-controls)
指出，GPU上下文建立后改变该掩码可能要求重启；模式还会跨重启保留。
切换前先结束实验进程并记录当前模式，重启后重新核对在线核数、频率和功耗模式。
`jetson_clocks`只在当前模式内锁定频率，不能代替模式切换；不修改热保护、硬件功率
限制或升级JetPack来替代本轮对照。回退模式为 `sudo nvpmodel -m 2`，同样可能需要重启。
功耗与散热原始配置快照见本轮证据目录的 `power_baseline.json`。

#### MAXN实测结果与候选配置

保持同一二进制、标定、530秒录包、10Hz图像、filter=4与leaf=0.15m，
依次只改变功耗模式与OpenMP线程上限。三轮导出的 `parameters.yaml` SHA-256一致，
二进制和标定摘要与15W基线一致。

| 模式 / OpenMP线程上限 | 运行期延迟P95 | 最大延迟 | CPU最高温度 | 结论 |
|---|---:|---:|---:|---|
| 15W / 2线程 | 11.50秒 | 16.95秒 | 54.7℃ | 持续积压 |
| MAXN / 2线程 | 2.19秒 | 5.96秒 | 57.1℃ | 明显改善，末段仍积压 |
| MAXN / 4线程 | 0.249秒 | 0.454秒 | 57.9℃ | 本轮530秒离线性能通过 |

MAXN/4线程输出约9.99Hz，算法RSS最高约4.27GiB；负载下已观测到1.984GHz。
LIO阶段耗时P95由15W/2线程的82.4ms降至55.5ms，VIO由34.8ms降至31.9ms；
阶段存在嵌套，不能把这些P95简单相加。额外核数和线程调度需要配合使用，
只提高模式并保留2线程仍未满足本轮实时要求。8核在线不代表算法独占或持续占满8核。

root只读监测的模块VDD_IN样本约6.5W均值、7.36W最高，部分采样窗口不完整，
该读数不包含整机电机和外设，不能当作整只机器狗功耗，也不是MAXN固定功耗。
没有修改风扇配置、硬件功率限制、热保护或JetPack版本。

通过的参数记录为 `profiles/maxn-balanced10.json`，板端独立候选目录为：
`/home/unitree/fast_livo2_port/onboard-iterations/performance-20261015-01/candidate-maxn-balanced10`。
它保存相同标定和点云参数，并引用既有诊断二进制；正式建图/导航入口没有被替换。
本轮尚未验证MAXN候选的实时传感器、移动精度或Nav2/MPPI同机负载。
15W/5Hz候选仍保留作为已通过静止实测的回退。

原始记录位于 `maxn-t2/`、`maxn-t4/`，汇总为 `power_comparison.json`，
曲线为 `power_comparison.png`。重新生成汇总：

```bash
python3 board/power_report.py board/evidence/performance-20261015-01
```

后续静止复测须使用 `live_probe.py --threads 4 --image-profile 10hz`，
确认静止并结束其他采集后运行。`live_probe.py` 默认仍为2线程，不会自动按模式加线程。

#### 录包尾部审计

本录包最后一帧雷达点的时间范围为1791946539.8789至1791946539.9789秒，
但JPEG和IMU还延续约1秒。最后有雷达覆盖的10Hz图像时间戳为1791946539.8963869；
三轮最终融合状态都达到该时刻。后续10张图像缺少对应雷达覆盖，不能继续融合。

旧回放工具在不同计算速度下，可能保留较早的profile年龄或在EOF后报告约1.09秒年龄；
因此原始日志中的“20秒后仍积压1.08秒”不单独构成处理积压证据。
15W/2线程与MAXN/2线程失败的依据是**传感器仍在输入时**分别达到16.95秒和5.96秒延迟。
MAXN/4线程不仅运行期延迟低于0.454秒，也独立核对到最后可融合图像已处理，
不是仅凭退出码0判定通过。该核对不表示EOF之后的所有同步缓存必须为空。
原始退出码/错误记录完整保留；审计数据见 `bag_tail_530s.json`。

### Go2W步态与到点切换审阅（2026-10-15）

本轮仅查询，没有切换步态、控制器或发布运动命令。使用实机SDK编译
`motion_probe/` 后调用 `CheckMode` 并订阅 `rt/lf/sportmodestate`，结果为
`check_mode_code=0`、`controller_form="1"`、`controller_name="ai-w"`，
观测31条状态，速度为零。`gait_type_raw=0`、`mode_raw=1`是原始状态字段，
不把它们直接等同于其他SDK接口的枚举。查询结果只证明当前身份，不枚举可切换模式。

[Go2W官方高层运动服务文档](https://support.unitree.com/home/zh/Go2-W_developer/sports_services)
（页面标注2026-04-08更新）列出以下步态：

| SwitchGait枚举 | 文档名称 | 场景 |
|---|---|---|
| 0 | 默认模式 | 平地、较简单地形 |
| 1 | 爬楼梯模式（地形行走） | 楼梯等复杂地形 |
| 2 | 爬高模式 | 规则高台、台阶等攀爬动作；区别于连续楼梯 |

同一文档在 `SwitchGait` 备注中明确写着 **“此接口暂不提供!”**。
实机使用的 `/home/unitree/go2w_slam_setup/sdk2/include/unitree/robot/go2/sport/sport_client.hpp`
也没有 `SwitchGait` 或 `GetState` 声明；官方当前Go2W示例中的相关调用仍为注释。
因此不能把旧Go2教程的步态3、通用AI/经典切换或原始RPC编号当作已验证的Go2W
自动爬楼接口。当前不调用这些接口，也不通过 `ReleaseMode` 释放正在维持站立的运控。

`ai-w` 是运控服务身份，与上表的三种步态不同。
[官方Go2W示例](https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2w/go2w_stand_example.cpp)
使用b2命名空间下的共享 `MotionSwitcherClient::CheckMode` 查询该身份。
只读查询程序没有复制该示例中的 `ReleaseMode` 和低层电机控制部分。

补充核对：实机SDK头文件和静态库均包含 `MotionSwitcherClient::SelectMode(nameOrAlias)`，
因此不能把 `SwitchGait` 的限制概括成“高层不能切换任何运控模式”。
`SelectMode` 选择运控服务/控制器身份，`SwitchGait` 切换步态，是不同层次的接口。
目前只实测了 `CheckMode`，尚未调用 `SelectMode`，也未确认本机可接受的其他模式名；
`ai-w` 身份不代表爬楼梯步态，不能猜测 `stairs`、`normal` 等字符串进行切换。
`SportClient::ClassicWalk` 等通用Go2方法虽存在于库中，也未证明Go2W固件支持其目标行为。

在台阶步态接口尚未验证前，到点动作的临时方案是人工确认检查点：本段闭环到位并受保护停车 → 停稳 →
提示目标步态 → 用户用App/遥控器切换 → 确认并重新验证定位/静止状态 → 下一段重新规划。
若确认了适用于本机固件的高层切换接口及可回读状态，可替换为自动请求并核对返回码和
目标状态后继续；不需要为了到点切换本身改成低层关节控制。
设置应绑定到路线中某一次经过的位置，避免重复经过同名点时错误复用动作。
动作变更须使旧路线预演失效，取消或状态丢失时不进入下一段。

官方描述 `StopMove` 会恢复部分默认参数；切换流程应安排在停车完成之后，
不能假定下一次停车后步态仍被保留。具体哪些参数被恢复尚未实测。
到点动作与二维Nav2的地形规划是两件事：自动切换步态不会使当前二维膨胀图自动理解
楼梯、负障碍或跨楼层连接；尚未验证的台阶段不能直接当作普通平地路段自主执行。

上述只读审阅阶段没有修改路线执行器。随后已按用户要求添加每点的 `arrival_motion`
参数、菜单3/17保存选择与菜单18编辑，并接好停车后的切换/回读/再停稳接口；
真实SDK实现位于 `navigation/mppi/go2w_mode_adapter.py`，当前能力集合仍为空，
选择切换的任务会在出发前拒绝执行，未启用未经验证的实机调用。
使用方法见项目《交互演示控制台使用说明》的“途经点参数”部分。
只读探针保存在板端 `onboard-iterations/motion-probe-20261015-01/`；
功耗仍为MAXN，正式运动保护程序未被替换。

## 回退

本次实验没有替换原板端默认算法。停止独立回放后，原有入口仍指向 `build1/ws`。
恢复实机采集须重新确认停稳；跨会话目标必须经过旧地图重定位，不自动恢复运动。

## 来源与许可

FAST-LIVO2补丁保留原GPLv2约束；原创新增诊断/独立CUDA累加实现按文件MIT说明。
组合二进制的分发仍受所有依赖许可约束。用户提供的NX参考仓库只作差异审阅，详见
[参考仓库审阅](参考仓库审阅_20260930.md)。
