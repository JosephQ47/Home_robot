# ROS 节点与技术方案对应表

本文只记录代码与《家庭服务机器人技术方案》的对应关系，不修改正式技术方案。
ROS 运行时节点名优先采用方案中的名称；硬件替代件和临时联调节点使用明确后缀。

| 技术方案模块 | ROS 包 | 运行时节点 | 主要接口 | 当前说明 |
|---|---|---|---|---|
| 任务管理器 `hr_task_manager` | `hr_task_manager` | `/hr_task_manager` | `/task/execute`、`/task/status`、任务策略 | 名称一致 |
| 目标跟踪 `hr_target_tracker` | `hr_target_tracker` | `/hr_target_tracker` | `/detections` → `/follow_target` | 名称一致；HMMD为临时单人关联模式 |
| 上下位机桥 `hr_bridge` | `hr_bridge` | `/hr_bridge` | `/cmd_vel`、`/wheel/odom_raw`、`/imu/data`、`/robot_status` | 名称一致 |
| 相机驱动 | `hr_camera` | `/hi3516_camera_driver` | `/camera/image_raw` | 当前兼容RTSP，正式目标仍是Hi3516 UVC |
| 视觉识别 | `hr_perception` | `/hr_perception` | `/camera/image_raw` → `/detections` | 对应方案“视觉识别” |
| 雷达驱动 | `hr_hmmd` | `/hmmd_radar_driver` | `/hmmd/detection` | 当前HMMD替代件；不等同正式RPLIDAR `/scan` |
| EKF | `hr_localization` | `/ekf_filter_node` | `/wheel/odom_raw`、`/imu/data` → `/odometry/filtered` | 使用标准 `robot_localization` 名称 |
| SLAM | `hr_localization` | `/slam_toolbox` | `/scan`、TF → `/map` | 正式方案入口，当前硬件阻塞 |
| AMCL | `hr_localization` | （计划）`/amcl` | `/map`、`/scan`、TF | 配置与运行节点尚未接入 |
| Nav2 | `hr_navigation` | （计划）`/planner_server`、`/controller_server`、`/bt_navigator` 等 | Nav2 Action → `/cmd_vel_auto` | 当前仅有配置骨架，正式节点组尚未接入 |
| Nav2短程联调替身 | `hr_local_motion` | `/nav2_local_controller_adapter` | `/goal_pose`、`/follow_target` → `/cmd_vel_auto` | 仅PC无地图联调；不作为正式独立控制器 |
| Collision Monitor | `hr_navigation` | `/collision_monitor` | `/cmd_vel_auto` → `/cmd_vel` | 名称和速度链一致 |
| 网页适配 | `hr_web_ui` | `/hr_web_ui` | HTTP ↔ `/task/execute`、状态话题 | 对应方案网页任务入口 |
| Mock系统 | `hr_simulation` | `/hr_mock_system` | Mock状态、里程计、IMU、扫描和Nav2 Action | 仅测试，不属于正式部署图 |

## 下位机名称

下位机尚未创建或烧录代码。后续 FreeRTOS 任务名直接采用技术方案：
`monitor_task`、`chassis_task`、`imu_task`、`command_task`，不另起别名。

## 固定速度链

```text
正式：Nav2 controller_server → /cmd_vel_auto → collision_monitor → /cmd_vel → hr_bridge

当前联调：nav2_local_controller_adapter → /cmd_vel_auto
          → collision_monitor/测试接收端（不连接真实底盘）
```

`nav2_local_controller_adapter` 在 `robot_bringup.launch.py` 中默认关闭。完成地图、传感器和
Nav2验收后停用该适配器，由正式 Nav2 节点组接管相同的 `/cmd_vel_auto` 接口。
