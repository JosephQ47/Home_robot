# ROS 节点与技术方案对应表

本文只记录代码与《家庭服务机器人技术方案》的对应关系，不修改正式技术方案。
ROS 运行时节点名优先采用方案中的名称。

**验证方式图例**：
🟢 实机运行 ·
🔵 链路验证（整条链路在 ROS graph 上跑通，有落盘证据） ·
🟣 自动化覆盖（单元测试覆盖全部行为规则） ·
⚪ 已接线（节点组与生命周期编排就位，拓扑可检查）

## 上位机（RK3588 / ROS 2 Humble）

| 技术方案模块 | ROS 包 | 运行时节点 | 主要接口 | 验证 | 做到了什么 |
|---|---|---|---|---|---|
| 任务管理器 | `hr_task_manager` | `/hr_task_manager` | `/task/execute`、`/task/status`、`/task/motion_phase` | 🔵 | 四类来源（SCHEDULE/WEB/VOICE/SYSTEM_BATTERY）互斥仲裁；阶段授权 5 Hz 持续续发，停发即归零；`ARM_STOP` 可在任务运行中被受理 |
| 深度相机驱动 | `hr_camera` | `/hr_camera` | `/camera/color/image_raw`、`/camera/depth/points`、`CameraInfo` | ⚪ | Gemini 2 彩色 1280×720@30、深度 848×480@30、点云与帧同步误差门限 |
| 视觉识别 | `hr_perception` | `/hr_perception` | `/camera/color/image_raw` → `/detections` | 🟣 | YOLO 二维检测与事件门控，输出 `Detection2DArray` |
| 深度障碍处理 | `hr_depth_obstacle` | `/hr_depth_obstacle` | `/camera/depth/points` → `/obstacle/depth_points` | 🟣 | 新鲜度、有效率、量程、地面滤除、高度窗口五级门控；深度空洞按未知处理，不清除既有障碍 |
| 目标跟踪 | `hr_target_tracker` | `/hr_target_tracker` | `/detections` → `/follow_target` | 🟣 | 同帧深度优先估距，深度失效回落 S3 角窗交叉验证 |
| 雷达驱动 | （上游 `sllidar_ros2`） | `/sllidar_node` | `/scan` | ⚪ | RPLIDAR S3，配置在 `hr_localization` |
| EKF | `hr_localization` | `/ekf_filter_node` | `/wheel/odom_raw`、`/imu/data` → `/odometry/filtered` | ⚪ | `odom→base_link` 的唯一发布者 |
| SLAM 建图 | `hr_localization` | `/slam_toolbox` | `/scan`、TF → `/map` | ⚪ | 异步建图入口，与 AMCL 模式强制互斥 |
| 地图定位 | `hr_localization` | `/amcl` + `/map_server` | `/map`、`/scan`、TF | ⚪ | 差速运动模型，里程计噪声按 1560 count/rev 编码器分辨率取值；缺地图参数时明确报错 |
| Nav2 | `hr_navigation` | `/planner_server`、`/controller_server`、`/behavior_server`、`/bt_navigator`、`/waypoint_follower` | Nav2 Action → **`/cmd_vel_nav`** | ⚪ | 五节点 + lifecycle_manager 编排；DWB 速度上限 0.45 m/s、减速 1.5 m/s²，与停止区尺寸同源 |
| AprilTag 检测 | （上游 `apriltag_ros`） | `/apriltag_node` | RGB → `/detections` + Tag TF | ⚪ | tag36h11，100 mm 印制尺寸，二分之一分辨率检测 |
| 充电桩定位 | `hr_docking` | `/hr_dock_pose_adapter` | `/detections` + TF + `CameraInfo` → `/detected_dock_pose` | 🔵 | ID / family / 汉明距离 / 判决裕度 / 位姿跳变 / TF 新鲜度六重门控；位姿由 TF 取，Tag—触点偏置换算后输出 |
| 精对接 | （上游 `opennav_docking`） | `/docking_server` | `DockRobot` → `/cmd_vel_dock` | ⚪ | 低速前向对接，速度仅经 `hr_motion_mux` 进入安全链 |
| 自动速度仲裁 | `hr_motion_mux` | `/hr_motion_mux` | `/cmd_vel_nav` + `/cmd_vel_dock` → **唯一 `/cmd_vel_auto`** | 🔵 | 阶段互斥选择，切换先归零 300 ms，源过期或授权过期即归零（[mux](acceptance/hr_motion_mux验收.md) · [全链](acceptance/速度链路验收.md)）|
| Collision Monitor | `hr_navigation` | `/collision_monitor` | `/cmd_vel_auto` + `/scan` → `/cmd_vel` | 🔵 | 0.50×0.60 m 激光停止区，由轮廓 + 171 ms 延迟行程 + 制动距离 + 余量推得；障碍进入即请求零速 |
| 上下位机桥 | `hr_bridge` | `/hr_bridge` | `/cmd_vel`、`/wheel/odom_raw`、`/imu/data`、`/robot_status`、`/battery_state` | 🟢 | CRC16 + 序号 + 心跳；断链重连与命令超时归零实机验证 |
| 网页任务入口 | `hr_web_ui` | `/hr_web_ui` | HTTP/WS ↔ `/task/execute` | 🔵 | 地图/区域/目标/模式下发，任务队列实时回写；Mock 与 ROS 双适配器 |
| 机械臂控制 | `hr_arm_controller` | `/hr_arm_controller` | `/arm/execute` Action → `/arm/joint_trajectory` | 🔵 | 抓取状态机 + 六轴解析逆运动学（FK/IK 往返误差 1e-16）+ 四重底盘互锁（[验收](acceptance/机械臂链路验收.md)）|
| 机械臂视觉 | `hr_arm_perception` | `/hr_arm_perception` | D435i RGB-D + `Detection2DArray` → `/arm/grasp_candidates` | 🔵 | 手眼标定有效性校验、深度密度/一致性门控、受限平面抓取候选；反投影落在针孔模型解析值上 |
| 机械臂驱动 | `hr_arm_driver` | `/hr_arm_driver` | `/arm/joint_trajectory` → 舵机控制器；`/arm/joint_states` | 🔵 | 长度前缀 + CRC16 帧协议，半帧/粘包/乱序可重同步；serial 与 mock 双传输 |
| 语音采集 | `hr_voice_capture` | `/hr_voice_capture` | 麦克风/文本 → `/voice/transcript_in` | 🔵 | 唤醒门（一次唤醒一条命令、窗口到期自动关闭）+ 可替换 ASR 适配器（[验收](acceptance/语音链路验收.md)）|
| 语音指令映射 | `hr_voice_command` | `/hr_voice_command` | 转写 → `ExecuteTask(source=VOICE)` | 🟣 | 十一条白名单命令的意图映射与全部拒绝路径；不发布任何速度或舵机接口 |
| Nav2 短程联调替身 | `hr_local_motion` | `/nav2_local_controller_adapter` | `/goal_pose`、`/follow_target` → `/cmd_vel_nav` | 🟣 | PC 无地图联调用，默认关闭，下游不在即拒绝输出 |
| Mock 系统 | `hr_simulation` | `/hr_mock_system` | Mock 状态、里程计、IMU、扫描和 Nav2 Action | 🟣 | 全链软件测试入口，不发布速度 |
| 机器人模型 | `hr_description` | `/robot_state_publisher` | URDF → TF | ⚪ | 坐标系与固定变换 |

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
