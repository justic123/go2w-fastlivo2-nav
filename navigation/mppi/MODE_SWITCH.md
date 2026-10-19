# Go2W 到点模式切换

实现路径：到达目标 → 已确认 StopMove 成功和静止 → 独占 point_trial.lock → 官方 B2 SportClient.SwitchGait → 独立 DDS 状态回读 → 再次静止确认 → 下一段。

本项目只提供请求 0（默认）与 1（地形/普通越障），不提供攀高、翻转、阻尼等动作。请求 1 与 App“普通越障”的对应关系必须在当前机器上验证。模式切换不等于已实现连续楼梯规划。

## 为什么需要兼容客户端

核对日期：2026-10-16。
- 官方 Go2W 文档定义 SwitchGait(0/1/2)，同时标注暂不提供：https://support.unitree.com/home/zh/Go2-W_developer/sports_services
- 官方 Go2 头文件没有 SwitchGait，Go2W 示例也注释了该调用：https://github.com/unitreerobotics/unitree_sdk2/blob/main/example/go2w/go2w_sport_client.cpp
- 官方 B2 客户端保留 SwitchGait，请求服务 sport、API 1011；官方仓库 issue #134 有 Go2W 用户报告采用 B2 客户端成功。该报告仅作为兼容线索，不能代替实机验证：https://github.com/unitreerobotics/unitree_sdk2_python/issues/134

## 验证与启用

`guard/build/go2w_mode_bridge eth0 --observe` 仅采集状态，最多300秒，不发模式或速度指令。

切换入口是 `--switch 0` 或 `--switch 1`，仅供已明确准备好的静止调试使用。程序需获取与运动控制共用的锁，并等待持续1秒、数据年龄小于0.2秒的静止反馈，RPC超时1秒；最多8秒自动退出。禁止通过批量尝试未知枚举发现模式。

只有核对 App 默认/普通越障反馈、验证实际 SDK 双向切换及反馈后，才写入板端 `board/calibration/motion_modes.json`：verified、machine_id、binary_sha256、api、request、feedback_gait。该文件是机器专用校验证据，不作为可复制的通用开启开关。未验证、二进制变化、机器不匹配、反馈枚举重复时不启用。

网页从适配器动态读取能力，不再硬编码禁止。每个目标的到点动作保存在地图目标文件中；改变动作后需要重新预演。SDK 成功码不足以继续，必须取得 RPC 回复之后独立到达的 DDS 状态。取消、超时、错误反馈或未停稳均终止后续路线。

## 当前实机结果（2026-10-16）

App 对照：默认 gait_type=0，普通越障 gait_type=1，sport_mode=1。兼容 SDK 原地三次请求：0→1→0，全部返回0，并获得对应独立DDS反馈。最后一次由正式 Python 适配器完成，状态已恢复默认。日志保存于板端 board/evidence/mode-20261016/。已启用当前机器的能力文件；未发送 Move 或转向指令，尚未做导航到点后切换的运动联调。当前导航默认0.2m/s。官方地形模式前进速度上限0.7m/s，不应沿用0.8m/s大厅档位进行地形导航。

含普通越障切换的任务在出发前检查速度档位；hall08（0.8m/s）会拒绝，需用corridor04或baseline重新预演。切换前再次检查，防止运行中更改配置。

2026-10-18修复（已部署，待运动联调）：到点可勾选manual_handoff，作为路线末点交给人工；此参数不代表楼梯控制。SDK等待与DDS确认分别计时。hall08守护还将核对实时默认步态，旧守护不支持该检查时客户端拒绝高速任务。StopMove是否重置步态仍需实机核对，不把“不切换”解释为强制保持某个步态。
