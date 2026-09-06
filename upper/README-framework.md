# ROS 2 上位机框架

正式部署目标是 RK3588/Ubuntu 22.04/ROS 2 Humble；当前 PC 虚拟机用于接口和 Mock 联调。

## 包与职责

| 包 | 当前职责 |
|---|---|
| `hr_interfaces` | 自定义消息和 `/task/execute` Action 的唯一来源 |
| `hr_description` | 机器人描述骨架；实测外参完成前只包含 `base_link` |
| `hr_camera` / `hr_vision` | synthetic、RTSP、V4L2 图像输入和现有 CPU YOLO |
| `hr_perception` | 感知后端选择和任务启停门控 |
| `hr_hmmd` | 微雪 HMMD UART 存在/粗距离帧；不发布 `/scan` |
| `hr_target_tracker` | 正式相机/平面扫描骨架与临时单人视觉/HMMD关联；默认关闭 |
| `hr_bridge` | STM32 协议边界；默认禁用串口和命令输出 |
| `hr_localization` | EKF、SLAM、AMCL 配置骨架 |
| `hr_navigation` | Nav2/Collision Monitor 配置和失败闭锁 BT 占位 |
| `hr_local_motion` | `/nav2_local_controller_adapter`：RViz `odom` 短程联调替身；默认不启动 |
| `hr_task_manager` | 任务 Action、互斥、准入、取消、超时和接管中断 |
| `hr_web_ui` | 现有网页后端与 ROS Action/状态的适配层 |
| `hr_simulation` | 不接硬件、不发速度的状态/传感/Nav2 Mock |
| `hr_bringup` | `mock`、`vision_rtsp`、`mapping`、`navigation`、`robot` 入口 |

## 构建与安全 Mock

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python -m colcon build --symlink-install
source install/local_setup.bash
export ROS_DOMAIN_ID=61 ROS_LOCALHOST_ONLY=1
ros2 launch hr_bringup mock.launch.py
```

Mock 模式中的 `/scan`、TF、里程计、IMU 和 Nav2 Action 都是测试数据。该模式不存在 `/cmd_vel` 或 `/cmd_vel_auto` 发布者。

短程目标和跟随控制的安全 Mock 验收：

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python ../tools/verify_motion_chain.py
python ../tools/verify_task_lifecycle.py
python ../tools/verify_bridge_pty.py
```

脚本启动 `chain_validation.launch.py`，验证 `/goal_pose`、目标跟随、目标超时停车、障碍停车和
唯一速度通道。它强制关闭 `hr_bridge` 传输和命令输出，不接触真实串口。
任务生命周期脚本另行验证 Action 完成、忙碌拒绝、前置条件拒绝、取消、超时和接管中断。
伪串口脚本验证 `hr_bridge` 的真实字节收发、限速和命令超时，全程使用 `/dev/pts/*`。

## 启动入口

- `mock.launch.py`：全框架软件联调。
- `vision_rtsp.launch.py source:=rtsp://... backend:=cpu_yolo model:=/abs/model.pt`：已验证 RTSP/CPU YOLO 路径。
- `mapping.launch.py`：真实建图入口，当前会因二维扫描硬件和部分依赖缺失而保持不可用。
- `navigation.launch.py`：真实导航入口，必须在地图、TF、二维扫描、Collision Monitor 和制动参数冻结后使用。
- `robot.launch.py`：实机组合入口；STM32、HMMD 和命令输出默认关闭。

无地图短程模式接收 RViz `/goal_pose`，只接受 `odom` 坐标系且默认上限 0.5 m、
5 s、0.10 m/s。`hr_local_motion` 仅向 `/cmd_vel_auto` 发布，并要求订阅端节点名为
`collision_monitor`；STM32 安全许可、轮式里程计、看门狗或数据新鲜度失效时持续
输出零速度。该节点只有在 `robot.launch.py local_motion_enabled:=true` 时才会出现，
当前不要在实车上启用。

启用 HMMD 串口前，先确认设备路径、电平、供电和距离字段单位。即使 HMMD 正常工作，也不能把 `/hmmd/detection` 重映射为 `/scan`。

任务状态和后续顺序见 [项目任务清单](../docs/项目任务清单.md)。
代码、运行时节点与正式方案的名称关系见
[ROS节点与技术方案对应表](../docs/ROS节点与技术方案对应表.md)。
