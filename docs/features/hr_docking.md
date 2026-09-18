# 功能设计：hr_docking（AprilTag 充电桩定位与 OpenNav Docking 集成）

- 状态：待评审
- 基准条款：技术方案 §1「自主充电」、§3.1.2、§3.1.4、§7.1、§10.1 步骤 11–12、§10.3「AprilTag精对接 / 充电真实性 / 对接安全链」
- 起草：AI；签字：__________ 日期：__________

## 1. 范围

本包**只**负责把 `tag36h11` 的检测结果，换算成 OpenNav Docking 需要的充电桩对接位姿
`/detected_dock_pose`，并提供充电桩数据库与对接参数配置。

精对接闭环由 Humble 的 `opennav_docking` 执行，本包不实现对接控制律；
充电成功判据由 `/battery_state` 决定，本包不宣告充电成功。

## 2. 节点划分

| 节点 | 来源 | 职责 |
|---|---|---|
| `/apriltag_node` | 上游 `apriltag_ros` | 从 Gemini 2 RGB + `CameraInfo` 检测 tag36h11 |
| `/hr_dock_pose_adapter` | **本包新增** | Tag 位姿门控 + Tag→触点偏置换算 + 超时失效，输出 `/detected_dock_pose` |
| `/docking_server` | 上游 `opennav_docking` | `DockRobot`/`UndockRobot` Action，输出 `/cmd_vel_dock` |

## 3. `hr_dock_pose_adapter` 接口契约

| 方向 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 订阅 | `/detections/apriltag` | `apriltag_msgs/AprilTagDetectionArray` | Tag 检测结果 |
| 订阅 | `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 内参有效性检查 |
| 发布 | `/detected_dock_pose` | `geometry_msgs/PoseStamped` | 充电桩对接位姿（`map` 或 `odom` 坐标系，按 Docking 配置） |
| 发布 | `/docking/tag_status` | `diagnostic_msgs/DiagnosticArray` | Tag 可见性、ID 匹配、位姿跳变、过期原因 |
| TF | `base_link → camera_link` | static | 由标定冻结，不得尺量近似 |

## 4. 行为规则（逐条可判定）

| 编号 | 规则 |
|---|---|
| DOCK-1 | 只接受 `docks.yaml` 中登记的 `tag_id`；其余 ID 一律丢弃并计数，不发布位姿。 |
| DOCK-2 | Tag 检测时间戳超过 `tag_timeout_ms` 即停止发布 `/detected_dock_pose`；**绝不复用旧位姿**。 |
| DOCK-3 | 相邻两帧位姿平移跳变超过 `max_jump_xy_m` 或航向跳变超过 `max_jump_yaw_rad` 时，判为异常，丢弃并计数；连续 `max_consecutive_jumps` 次异常则进入失效态。 |
| DOCK-4 | `CameraInfo` 缺失、内参全零或畸变模型不匹配时拒绝输出。 |
| DOCK-5 | 输出位姿 = Tag 位姿 × `tag_to_contact` 偏置（外参由实测标定冻结，写在 `docks.yaml`）。 |
| DOCK-6 | 检测到 Tag **不代表**已接触、也不代表正在充电；本节点不发布任何充电状态。 |
| DOCK-7 | 需要连续 `min_consecutive_detections` 帧有效检测才首次发布，避免单帧误检驱动对接。 |

## 5. 配置文件

```text
hr_docking/config/
├─ apriltag.yaml    # family=tag36h11、允许 ID 列表、实际边长、检测门限
├─ docks.yaml       # dock_id、map 预停靠位、tag_id、tag_to_contact 偏置
└─ docking.yaml     # 对接速度、容差、超时、重试次数、充电确认阈值
```

## 6. 与安全链的关系（不可协商）

回充全过程 **保持** S3 `/scan`、Collision Monitor、命令超时与 STM32 限制有效。
`/cmd_vel_dock` 只能进入 `hr_motion_mux`，不得直接发布 `/cmd_vel`。

若充电桩机械设计导致触点接通前就被停止区永久阻挡，**禁止关闭或缩小安全链**，
必须返回机械/碰撞策略评审（技术方案 §10.3「对接安全链」）。

## 7. 验收标准

| 编号 | 判据 | 证据形式 |
|---|---|---|
| AC-1 | 静止底盘上，在冻结的距离/横向偏差/照度组合内记录位姿误差统计 | 实测表格 + 原始 bag |
| AC-2 | 注入错误 Tag ID，`/detected_dock_pose` 无输出 | 单元测试 |
| AC-3 | 停止 Tag 检测后 `tag_timeout_ms` 内停止发布，且不复用旧位姿 | 单元测试 |
| AC-4 | 注入超限位姿跳变，节点丢弃并进入失效态 | 单元测试 |
| AC-5 | ROS graph 中 `/cmd_vel` 的 publisher 只有 Collision Monitor | 图检查脚本 |
| AC-6 | 接触但无充电电流时执行后退重试；超过冻结次数后停车告警 | 实测记录 |
| AC-7 | 充电成功仅由持续充电电流或经验证 BMS 状态判定，位姿/接触均不单独成立 | 实测记录 |

## 8. 分阶段实施（按技术方案 §10.1 步骤 11–12，不得跳步）

1. **静止验收**：只跑 AprilTag + adapter，底盘不动，验收位姿精度与失效逻辑。
2. **断电机械对接**：断开充电电源，低速验证机械导向与触点接通。
3. **限流台架电源**：验证接触导通与保护。
4. **接入匹配充电器/BMS**：验证真实充电、重试与充电确认。

## 9. 本次交付边界

本次仅交付 `hr_dock_pose_adapter` 节点 + 三份配置骨架 + 单元测试。
`opennav_docking` 的接入、充电桩实物标定外参、`docks.yaml` 实测数值均**待硬件到位后冻结**。
