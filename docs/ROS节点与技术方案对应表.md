# ROS 节点与技术方案对应表

本文只记录代码与《家庭服务机器人技术方案》的对应关系，不修改正式技术方案。
ROS 运行时节点名优先采用方案中的名称；硬件替代件和临时联调节点使用明确后缀。

**成熟度图例**：
🟢 已实测 ·
🟡 已实现待实测 ·
🔵 骨架（可构建、逻辑有测试、硬件未到位） ·
⚪ 仅配置 ·
⛔ 历史替代件，不属于正式方案

## 上位机（RK3588 / ROS 2 Humble）

| 技术方案模块 | ROS 包 | 运行时节点 | 主要接口 | 成熟度 | 说明 |
|---|---|---|---|---|---|
| 任务管理器 `hr_task_manager` | `hr_task_manager` | `/hr_task_manager` | `/task/execute`、`/task/status`、`/task/motion_phase` | 🟡 | 名称一致；已按新方案发布 `DOCKING` 阶段与 `source_seq`，并 5 Hz 续发授权 |
| 深度相机驱动 | `hr_camera` | `/hr_camera` | `/camera/color/image_raw`、`/camera/depth/points`、`CameraInfo` | ⚪ | **方案已改为 Orbbec Gemini 2**；当前仍为 RTSP/文件取流的调试实现，Gemini 2 实物未接入 |
| 视觉识别 | `hr_perception` | `/hr_perception` | `/camera/color/image_raw` → `/detections` | 🟡 | CPU YOLO 已跑通；正式方案为 RKNN |
| 深度障碍处理 | `hr_depth_obstacle` | `/hr_depth_obstacle` | `/camera/depth/points` → `/obstacle/depth_points` | 🔵 | **新增**；门控/地面滤除逻辑已实现并有 11 条单元测试，阈值待实测冻结 |
| 目标跟踪 | `hr_target_tracker` | `/hr_target_tracker` | `/detections` → `/follow_target` | 🟡 | 方案已改为「优先同帧深度估距，深度无效才回落 S3 角窗」，深度分支待接入 |
| 雷达驱动 | （上游 `sllidar_ros2`） | `/sllidar_node` | `/scan` | ⚪ | RPLIDAR S3；配置在 `hr_localization` |
| EKF | `hr_localization` | `/ekf_filter_node` | `/wheel/odom_raw`、`/imu/data` → `/odometry/filtered` | 🟡 | 标准 `robot_localization`；`odom→base_link` 的唯一发布者 |
| SLAM | `hr_localization` | `/slam_toolbox` | `/scan`、TF → `/map` | ⚪ | 配置就位，待实机 |
| AMCL | `hr_localization` | `/amcl` + `/map_server` | `/map`、`/scan`、TF | ⚪ | 已接入 `localization.launch.py` 的 navigation 模式（需 `map:=`）；与 slam_toolbox 互斥；缺已验收地图 |
| Nav2 | `hr_navigation` | `/planner_server`、`/controller_server`、`/behavior_server`、`/bt_navigator`、`/waypoint_follower` | Nav2 Action → **`/cmd_vel_nav`** | ⚪ | 节点组与 lifecycle_manager 已接入 `navigation.launch.py`；速度/加速度/footprint 均为**占位值待实测冻结**，默认不启用 |
| AprilTag 充电桩定位 | `hr_docking` | `/hr_dock_pose_adapter` | AprilTag + `CameraInfo` → `/detected_dock_pose` | 🔵 | **新增**；ID 门控/超时/跳变/偏置换算已实现并有 11 条单元测试，Tag 与外参待实测 |
| AprilTag 检测 | （上游 `apriltag_ros`） | `/apriltag_node` | RGB → `/detections/apriltag` | ⚪ | 依赖包可由 `scripts/install_deps.sh docking` 安装；本机尚未安装 |
| 精对接 | （上游 `opennav_docking`） | `/docking_server` | `DockRobot` → `/cmd_vel_dock` | ⚪ | 依赖包可由 `scripts/install_deps.sh docking` 安装；充电桩未到位 |
| 自动速度仲裁 | `hr_motion_mux` | `/hr_motion_mux` | `/cmd_vel_nav` + `/cmd_vel_dock` → **唯一 `/cmd_vel_auto`** | 🟡 | **新增**；12 条单元测试 + 运行时验收（见 `docs/acceptance/hr_motion_mux验收.md`） |
| Collision Monitor | `hr_navigation` | `/collision_monitor` | `/cmd_vel_auto` → `/cmd_vel` | ⚪ | 名称与速度链一致；**停止区多边形仍为空**，待实测制动距离冻结 |
| 上下位机桥 | `hr_bridge` | `/hr_bridge` | `/cmd_vel`、`/wheel/odom_raw`、`/imu/data`、`/robot_status`、`/battery_state` | 🟡 | `/battery_state` 为新方案新增，待下位机电池帧接入 |
| 网页任务入口 | `hr_web_ui` | `/hr_web_ui` | HTTP/WS ↔ `/task/execute` | 🟡 | 前后端已跑通；Mock 与 ROS 两种适配器 |
| 机械臂控制 | `hr_arm_controller` | `/hr_arm_controller` | `/arm/execute` Action → `/arm/joint_trajectory` | 🟡 | **新增**；状态机 + 六轴 IK + Action 服务端均已实现；23 条 IK 测试 + 12 条状态机测试 + 6 项运行时验收（见 [机械臂链路验收](acceptance/机械臂链路验收.md)）；连杆长度为占位值 |
| 机械臂视觉 | `hr_arm_perception` | `/hr_arm_perception` | D435i RGB-D + 检测 → `/arm/grasp_candidates` | 🔵 | **新增**；标定校验、深度门控、抓取候选已实现，28 条单元测试；无有效手眼标定拒绝启动；D435i 未到位 |
| 机械臂驱动 | `hr_arm_driver` | `/hr_arm_driver` | `/arm/joint_trajectory` → 舵机控制器；`/arm/joint_states` | 🟡 | **新增**；帧协议 + CRC + 重同步已实现，14 条单元测试；`transport=mock` 可在 PC 跑通全链；真实控制器未选型 |
| 语音指令映射 | `hr_voice_command` | `/hr_voice_command` | 转写 → `ExecuteTask(source=VOICE)` | 🔵 | **新增**；白名单意图映射与拒绝策略已实现并有 12 条单元测试 |
| 语音采集 | `hr_voice_capture` | `/hr_voice_capture` | 麦克风/文本 → `/voice/transcript_in` | 🟡 | **新增**；唤醒门 + 可替换 ASR 适配器（text/vosk），12 条单元测试 + 6 项运行时验收（见 [语音链路验收](acceptance/语音链路验收.md)）；麦克风未选型 |
| Nav2 短程联调替身 | `hr_local_motion` | `/nav2_local_controller_adapter` | `/goal_pose`、`/follow_target` → `/cmd_vel_nav` | 🟡 | 仅 PC 无地图联调；默认关闭；输出已随新方案改为 `/cmd_vel_nav` |
| Mock 系统 | `hr_simulation` | `/hr_mock_system` | Mock 状态、里程计、IMU、扫描和 Nav2 Action | 🟡 | 仅测试，不属于正式部署图 |
| 机器人模型 | `hr_description` | `/robot_state_publisher` | URDF → TF | ⚪ | 需按 Gemini 2 与机械臂安装位更新 |
| 毫米波替代件 | `hr_hmmd` | `/hmmd_radar_driver` | `/hmmd/detection` | ⛔ | **新方案中不存在此链路**；保留为历史调试件，不纳入正式部署图 |
| 旧视觉调试件 | `hr_vision` | — | — | ⛔ | 历史调试件 |

## 下位机（STM32F407VET6 / FreeRTOS）

四个任务名直接采用技术方案，不另起别名：
`monitor_task`、`chassis_task`、`imu_task`、`command_task`。

技术方案新增的电池总压/充电状态采集与 `BatteryLevel` 分级归入 `monitor_task`，
经 `STATE_SLOW` 上行后由 `hr_bridge` 映射为 `/battery_state`。

## 固定速度链（新方案）

```text
Nav2          → /cmd_vel_nav  ┐
                              ├→ hr_motion_mux → /cmd_vel_auto → collision_monitor → /cmd_vel → hr_bridge → STM32
OpenNav Docking → /cmd_vel_dock ┘
```

关键约束：

- `/cmd_vel_auto` 的 publisher **有且只有** `/hr_motion_mux`。
- `hr_motion_mux` 按 `/task/motion_phase` 互斥选择，切换先归零，源过期即归零。
- 阶段是**授权**而非状态通知：`hr_task_manager` 必须持续续发，停发即归零。
- 任何回充速度**不得**绕过 Collision Monitor；STM32 仍是物理限速与执行的唯一权威。

`nav2_local_controller_adapter` 在 `robot_bringup.launch.py` 中默认关闭。
完成地图、传感器和 Nav2 验收后停用该适配器，由正式 Nav2 节点组接管相同的
`/cmd_vel_nav` 接口。

## 与旧版本的差异（本次按新技术方案更新）

| 项 | 旧 | 新 |
|---|---|---|
| 图像源 | Hi3516CV610 + SC4336P USB UVC | **Orbbec Gemini 2**（RGB + 深度 + 点云 + IMU） |
| 图像话题 | `/camera/image_raw` | `/camera/color/image_raw` 等 |
| Nav2 输出 | 直接发 `/cmd_vel_auto` | 发 `/cmd_vel_nav`，经 `hr_motion_mux` |
| 自动速度源 | 仅 Nav2 一路 | Nav2 与 Docking 两路，互斥仲裁 |
| 回充 | 无 | AprilTag + OpenNav Docking + BMS 充电确认 |
| 电池 | 无 | 带 BMS 成品电池包 + `/battery_state` + 低电分级 |
| 机械臂/语音 | 无 | 6 轴舵机臂 + 末端 D435i + 有限语音指令集 |
| 毫米波 `hr_hmmd` | 临时替代 `/scan` | 新方案中不存在，降级为历史件 |
