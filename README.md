# Home_robot

家庭服务机器人项目代码与调试资料仓库。

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

设计边界：

- 前端只通过 HTTP/WebSocket 和后端通信。
- 后端只创建、取消离散任务并推送状态。
- 后端不提供速度控制、摇杆控制、电机控制或 `/cmd_vel` 直通接口。
- 后续接入 ROS 2 时，将 `MockTaskAdapter` 替换成 `rclpy` 的 `/task/execute` Action Client。

## 测试

```powershell
python -m unittest discover -s web_control\backend -p test_*.py
```

## 后续计划

- 将 `hr_web_ui` 整理成 ROS 2 Python package。
- 用真实 `rclpy` Action Client 对接 `/task/execute`。
- 订阅 `/task/status`、`/robot_status`、`/follow_target` 等话题，并通过 WebSocket 推送到网页。
- 增加基础鉴权和局域网访问控制。
