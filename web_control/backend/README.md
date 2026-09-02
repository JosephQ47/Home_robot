# hr_web_ui backend

这个目录是 `web_control` 的 Python 后端首版实现。它负责把浏览器里的离散任务请求转换成后端任务对象，并通过 HTTP/WebSocket 给前端提供状态。

## 当前边界

- `GET /api/bootstrap`：页面初始化，返回地图、区域、目标类别、系统状态、任务记录和 WiFi 列表。
- `POST /api/tasks`：创建网页任务，字段包括 `map_id`、`area_id`、`target_class`、`mode`、`name`、`request_id`。
- `POST /api/tasks/{task_id}/cancel`：取消任务。
- `DELETE /api/tasks/{task_id}`：等价于先取消任务，再让前端移除显示记录。
- `POST /api/wifi/connect`：模拟切换 WiFi 显示状态。
- `GET /ws/status`：每秒推送系统状态、任务状态和 WiFi 状态。

后端不提供 `/cmd_vel`、速度、摇杆或电机控制接口。网页只能创建、取消离散任务和查看状态。

## 运行

```powershell
python web_control\backend\app.py --host 127.0.0.1 --port 8080
```

然后打开：

```text
http://127.0.0.1:8080/
```

## 后续接 ROS 2

当前 `MockTaskAdapter` 只是本地模拟。真机部署时把它替换成 `rclpy` 适配器：

- `submit()` 作为 `/task/execute` 的 Action Client 发送 Goal。
- `cancel()` 调用 `/task/execute` Cancel。
- WebSocket 快照从 `/task/status`、`/robot_status`、`/odometry/filtered` 和 `/follow_target` 更新。
