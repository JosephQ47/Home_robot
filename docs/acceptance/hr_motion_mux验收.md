# hr_motion_mux 运行时验收证据

- 日期：2026-09-18
- 环境：Ubuntu 22.04 / ROS 2 Humble / PC（非实机）
- 被测：`hr_motion_mux` 节点，参数取 `config/motion_mux.yaml` 首版值
- 判据来源：`docs/features/hr_motion_mux.md` §6

```text
MotionPhase.DOCKING = 3
--- ros2 topic info /cmd_vel_auto (AC-1) ---
Type: geometry_msgs/msg/Twist
Publisher count: 1
Subscription count: 1
AC-2 dock leaked under NAVIGATING: 0 (expect 0)
AC-2 nav forwarded: True (expect True)
AC-3 all zero inside the 300 ms switch hold: True (expect True)
AC-3 dock forwarded once the hold expired: True (expect True)
AC-4 zero after the source went quiet: True (expect True)
AC-5 zero after the authorisation expired: True (expect True)
AC-6 every published linear.y == 0: True (expect True)
```

## 本次验证发现的集成问题

首轮运行 AC-2/AC-4 未通过，排查后确认不是 `hr_motion_mux` 的缺陷，而是
`hr_task_manager` 只在状态迁移时发布一次 `/task/motion_phase`。

`hr_motion_mux` 把阶段当作**授权**处理，授权不续期即过期（MUX-4）——这正是
「任务管理器进程死掉后机器人必须停住」的实现方式。于是事件式发布会导致
**导航开始 1 秒后底盘被归零**。

修法是让 `hr_task_manager` 以 5 Hz 续发当前阶段，而**不是**放宽 mux 的超时：
授权本来就该续期，放宽超时等于让一个已经死掉的任务管理器继续授权运动。

续发时 `zero_required` 置 false——强制归零窗口属于「切换」这个事件本身，
每 200 ms 重申一次会把底盘永久按在零速。

## 尚未验证

- 与真实 Nav2 `controller_server` 的联调（需地图与实机）
- 与 `opennav_docking` 的联调（该包尚未安装，充电桩未到位）
- Collision Monitor 下游停止区（停止区多边形仍为空，待实测冻结）
