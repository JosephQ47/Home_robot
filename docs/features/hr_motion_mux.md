# 功能设计：hr_motion_mux（自动速度源互斥仲裁）

- 状态：待评审
- 基准条款：技术方案 §2.2、§3.1.2、§3.1.3、§3.1.4、§7.1、§10.3「速度单通道」
- 起草：AI；签字：__________ 日期：__________

## 1. 为什么需要

新技术方案引入自主回充后，自动速度出现**两个**来源：Nav2 的 `/cmd_vel_nav` 与 OpenNav
Docking 的 `/cmd_vel_dock`。当前代码里 Nav2 直接发布 `/cmd_vel_auto`，一旦接入 Docking
就会出现两个节点同时往同一话题写速度——ROS 2 不会报错，底盘会收到两路交替命令。
`hr_motion_mux` 是把「谁有权发速度」这件事显式化的唯一仲裁点。

它**不**做规划，**不**做限速，**不**替代 Collision Monitor，也不改变 STM32 的物理执行权威。

## 2. 接口契约

| 方向 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 订阅 | `/cmd_vel_nav` | `geometry_msgs/Twist` | Nav2 控制器输出；导航/巡检/跟随候选 |
| 订阅 | `/cmd_vel_dock` | `geometry_msgs/Twist` | OpenNav Docking 输出；仅 `DOCKING` 阶段候选 |
| 订阅 | `/task/motion_phase` | `hr_interfaces/MotionPhase` | 由 `hr_task_manager` 发布的授权阶段 |
| 发布 | `/cmd_vel_auto` | `geometry_msgs/Twist` | **唯一**自动速度输出，送入 Collision Monitor |
| 发布 | `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | 当前阶段、选中源、过期计数、归零原因 |

`MotionPhase.msg` 需新增 `DOCKING=3` 常量与 `uint32 source_seq` 字段（见 §5 变更清单）。

## 3. 行为规则（逐条可判定）

| 编号 | 规则 |
|---|---|
| MUX-1 | `phase=NAVIGATING` 或 `FOLLOWING` 时只允许转发 `/cmd_vel_nav`；`phase=DOCKING` 时只允许转发 `/cmd_vel_dock`；`phase=ZERO` 一律输出零速。 |
| MUX-2 | 阶段发生任何切换时，先连续发布 `zero_hold_ms` 时长的零速，之后才允许转发新源。切换期间到达的新源命令被丢弃，不排队。 |
| MUX-3 | 选中源的最近一条命令超过 `source_timeout_ms` 未更新即判定过期，输出零速并置诊断 `stale`。恢复必须等待新命令，不得复用过期值。 |
| MUX-4 | `/task/motion_phase` 本身超过 `phase_timeout_ms` 未更新，视为无授权，输出零速。 |
| MUX-5 | `source_seq` 回退或重复（旧阶段消息迟到）时忽略该阶段消息，不切换。 |
| MUX-6 | 输出的 `linear.y` 恒为 0（四轮差速底盘无横向速度）；`linear.z`、`angular.x/y` 同样恒为 0。 |
| MUX-7 | 未被授权的源即使持续发布也绝不转发，且不影响输出频率。 |
| MUX-8 | 节点以固定 `publish_rate_hz` 周期发布，即使输入静默也持续输出零速，使下游超时判据稳定。 |

## 4. 配置项（`config/motion_mux.yaml`）

| 参数 | 含义 | 首版取值 | 冻结依据 |
|---|---|---|---|
| `publish_rate_hz` | 输出周期 | 50 | 与 `CMD_MOTION` 50~100 Hz 对齐（§8.1） |
| `source_timeout_ms` | 速度源过期阈值 | 200 | 须小于 STM32 侧 150 ms 命令超时的恢复裕量，实测冻结 |
| `phase_timeout_ms` | 阶段授权过期阈值 | 1000 | 阶段为低频事件话题 |
| `zero_hold_ms` | 切换归零保持时长 | 300 | 须覆盖实测制动距离，台架冻结 |

> 上表数值为**待实测冻结**的初值，不得写入简历或答辩当作实测结论。

## 5. 需要一并变更的既有代码

1. `hr_interfaces/msg/MotionPhase.msg`：新增 `DOCKING=3`、`uint32 source_seq`。
2. `hr_navigation/config/nav2_params.yaml`：`controller_server.cmd_vel_topic` 由
   `/cmd_vel_auto` 改为 `/cmd_vel_nav`。
3. `hr_local_motion`（PC 联调替身）：输出由 `/cmd_vel_auto` 改为 `/cmd_vel_nav`，
   使联调链路与正式链路拓扑一致。
4. `hr_task_manager`：发布 `MotionPhase` 时填充 `source_seq`，并在回充阶段发 `DOCKING`。
5. `hr_bringup/launch/robot_bringup.launch.py`：在 Collision Monitor 之前拉起 `hr_motion_mux`。

## 6. 验收标准

| 编号 | 判据 | 证据形式 |
|---|---|---|
| AC-1 | `ros2 topic info /cmd_vel_auto` 显示**有且仅有一个** publisher，即 `/hr_motion_mux` | 终端输出落盘 |
| AC-2 | `phase=NAVIGATING` 下注入 `/cmd_vel_dock` 非零命令，`/cmd_vel_auto` 全程为零 | 单元测试 + bag |
| AC-3 | `NAVIGATING → DOCKING` 切换后，`/cmd_vel_auto` 在 `zero_hold_ms` 内连续为零 | 单元测试断言 |
| AC-4 | 选中源停发后 `source_timeout_ms` 内输出归零 | 单元测试断言 |
| AC-5 | `/task/motion_phase` 停发后输出归零 | 单元测试断言 |
| AC-6 | 全部输出的 `linear.y == 0.0` | 单元测试断言 |
| AC-7 | `colcon test --packages-select hr_motion_mux` 全绿 | `colcon test-result --verbose` |

## 7. 明确不做

不做速度平滑（方案明确不启用 Velocity Smoother）、不做加减速限幅（属 STM32）、
不做停止区判断（属 Collision Monitor）、不做源优先级抢占（阶段由任务管理器唯一决定）。
