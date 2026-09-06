# Home_robot

家庭服务机器人项目代码与调试资料仓库。

ROS 2 全框架说明见 [上位机框架](upper/README-framework.md)，节点与正式方案的关系见
[ROS节点与技术方案对应表](docs/ROS节点与技术方案对应表.md)，阶段依赖和实测/阻塞状态见
[项目任务清单](docs/项目任务清单.md)。安全 Mock 总入口为 `ros2 launch hr_bringup mock.launch.py`；该模式不连接硬件且不发布速度。当前替代传感器微雪 HMMD 通过独立 `hr_hmmd` 包接入，它不是二维激光雷达，也不发布 `/scan`。

用于快速验证技术方案的 STM32 下位机框架位于 [lower/](lower/README.md)，OpenCTR 厂商源码审查见
[OpenCTR V3.61 下位机源码审查](docs/OpenCTR_V3.61源码审查.md)。

PC/Ubuntu 视觉调试按技术方案 §9.2 归位：图像源在 `hr_camera`（当前 UVC 未打通，临时以 RTSP/文件取流），识别在 `hr_perception`（CPU YOLO），输出标准 ROS 2 图像、检测和诊断话题。启动、测试及其他节点准备状态见 [视觉调试说明](upper/README-vision.md)。该入口不启动底盘串口控制，正式 RK3588 技术方案保持不变。

海思资料核验与待交叉编译的最小程序见 [Hi3516 应用开发准备](hi3516/README.md)。资料归档和工具链仍放在 `/home/luckfox/Hi3516`，不混入 ROS 源码目录。

当前已提交 `web_control` 网页控制台，包括静态前端和 Python 后端首版实现。后端用于连接浏览器页面和后续 ROS 2 任务系统，当前阶段使用 Mock 适配器模拟机器人任务状态，方便先调通网页交互。

## 目录结构

```text
web_control/
├─ index.html                  # 网页控制台前端
├─ dashboard-desktop.png        # 桌面端效果图
├─ dashboard-mobile.png         # 移动端效果图
└─ backend/
   ├─ app.py                    # Python HTTP/WebSocket 后端
   ├─ test_app.py               # 后端单元测试
   └─ README.md                 # 后端接口说明
```

## 运行网页控制台

在项目根目录执行：

```powershell
python .\web_control\backend\app.py --host 127.0.0.1 --port 8080
```

然后在浏览器打开：

```text
http://127.0.0.1:8080/
```

如果你不在项目根目录，也可以使用绝对路径：

```powershell
python D:\Embedded\Home_robots\web_control\backend\app.py --host 127.0.0.1 --port 8080
```

注意路径是 `web_control`，下划线前面不需要加反斜杠。

## 后端接口

当前后端提供这些接口：

```text
GET    /api/bootstrap
GET    /api/status
POST   /api/tasks
POST   /api/tasks/{task_id}/cancel
DELETE /api/tasks/{task_id}
POST   /api/wifi/connect
GET    /ws/status
```

ROS Mock 总框架运行时，可在已 source 工作区的另一个终端启动真实 Action 适配：

```bash
python web_control/backend/app.py --adapter ros --host 127.0.0.1 --port 8080
```

默认 `--adapter mock` 保留原有纯网页演示模式。

设计边界：

- 前端只通过 HTTP/WebSocket 和后端通信。
- 后端只创建、取消离散任务并推送状态。
- 后端不提供速度控制、摇杆控制、电机控制或 `/cmd_vel` 直通接口。
- 使用 `--adapter ros` 时，由 `rclpy` Action Client 转发到 `/task/execute`；默认仍使用 `MockTaskAdapter`。

## 测试

```powershell
python -m unittest discover -s web_control\backend -p test_*.py
```

## 后续计划

- 将 ROS `/task/status`、`/robot_status`、`/follow_target` 的完整字段持续同步到 WebSocket 页面状态。
- 增加任务审计持久化、基础鉴权和局域网访问控制。
