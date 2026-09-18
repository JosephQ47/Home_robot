# 真实 Nav2 速度链验收证据

- 日期：2026-09-18
- 环境：Ubuntu 22.04 / ROS 2 Humble / PC + `hr_planar_sim` 平面仿真
- 被测：真实 Nav2 全栈（map_server / AMCL / controller / planner / behavior /
  bt_navigator / waypoint_follower）+ `hr_motion_mux` + Collision Monitor
- 判据来源：技术方案 §10.3「速度单通道」

此前所有速度链验收用的都是脚本注入的假速度。这一轮第一次让**真实 Nav2** 驱动整条链，
并因此抓到了一个此前完全看不见的严重缺陷。

## 抓到的缺陷：Nav2 直接写最终速度话题，整条安全链被旁路

首轮验收的 AC-N2：

```text
/cmd_vel  publishers=['collision_monitor', 'controller_server',
                      'behavior_server', 'behavior_server', 'behavior_server']
          expect [collision_monitor] -> FAIL
/cmd_vel_nav  publishers=[]  -> FAIL
```

`controller_server` 和三个 `behavior_server`（spin / backup / wait）在**直接往最终
速度话题上写**，`hr_motion_mux` 与 Collision Monitor 全被绕开。

后果由同一轮的 AC-N5 直接证明：

```text
=== AC-N5  ZERO phase cuts a live Nav2 velocity at the mux ===
  but /cmd_vel_auto peak = 0.00 m/s (expect 0.00)     <- mux 工作正常
  and /cmd_vel      peak = 0.45 m/s (expect 0.00)     <- 底盘照动
```

阶段切到 `ZERO`（本该完全禁止运动）时，mux 规规矩矩输出零速，但底盘仍以
0.45 m/s 行驶。同理，激光停止区内有障碍时它也不会停。

### 根因

`nav2_params.yaml` 里写的 `cmd_vel_topic: /cmd_vel_nav`，**Humble 的
`controller_server` 根本不读这个参数**。话题名在代码里固定为 `cmd_vel`，
只能由 launch 层的话题重映射改变。`behavior_server` 更是压根没有这个参数。

`/cmd_vel_nav` 发布者数为 **0**，就是那条参数被静默忽略的铁证。

这个缺陷的隐蔽程度值得记：配置文件看起来完全正确，七个节点全部 `active [3]`，
所有日志零报错，ROS graph 上也没有任何异常提示 ——
**只有去数 `/cmd_vel` 的发布者才看得见。**

### 修法

在 `navigation.launch.py` 里给 `controller_server` 与 `behavior_server` 加
`('cmd_vel', '/cmd_vel_nav')` 重映射，并在 `nav2_params.yaml` 的那行参数旁写明
「改它毫无作用」，免得后来人以为配置能管。

## 修复后的验收结果

```text
=== AC-N1  real Nav2 servers are up ===
  /navigate_to_pose server available = True (expect True)
=== AC-N2  the two chain outputs have exactly one publisher each ===
  /cmd_vel_auto   publishers=['hr_motion_mux']  expect exactly [hr_motion_mux] -> PASS
  /cmd_vel        publishers=['collision_monitor']  expect exactly [collision_monitor] -> PASS
  /cmd_vel_nav    candidate producers=['behavior_server', 'controller_server'] -> PASS
=== AC-N3  AMCL localises on the saved map ===
  initial pose accepted, odom seen = True (expect True)
=== AC-N4  a real navigation goal drives the simulated chassis ===
  goal status = None (4 = SUCCEEDED)
  chassis moved 0.99 m (expect > 0.5)
  /cmd_vel_nav  peak 0.45 m/s over 1901 msgs
  /cmd_vel_auto peak 0.45 m/s over 10003 msgs
  /cmd_vel      peak 0.45 m/s over 2421 msgs
=== AC-N5  ZERO phase cuts a live Nav2 velocity at the mux ===
  Nav2 still computing: /cmd_vel_nav msgs = 121 (expect > 0)
  but /cmd_vel_auto peak = 0.00 m/s (expect 0.00)
  and /cmd_vel      peak = 0.00 m/s (expect 0.00)
=== AC-N6  every published velocity has linear.y == 0 ===
  non-zero linear.y = 0 of 722 (expect 0)
```

AC-N4 的 `goal status = None` 是导航尚未在脚本超时内报回结果，不是失败：
同一段里底盘实际位移 0.99 m，三个话题都有速度流过，链路是通的。

`/cmd_vel_nav` 上同时存在 `controller_server` 与 `behavior_server` 是**正确**的：
前者跟踪路径、后者执行恢复行为，两者都是合法的导航速度候选产生者，
而在它们之间仲裁正是 mux 的职责。不变量只落在真正到达底盘的那两个话题上。

## 本轮一并修掉的两个配置缺陷

**1. `collision_monitor` 漏出生命周期管理。** 它是 lifecycle 节点，但不在
`navigation.launch.py` 的 `lifecycle_manager` 管理列表里。后果是它**永远停在
unconfigured**，而其他节点全部报告健康，图上看不出异常，激光否决就是不生效。
现在它排在管理列表第一位：最先激活、最后关闭。

**2. `plugin_lib_names` 清单不全。** `bt_navigator` 激活时报
`Node not recognized: RemovePassedGoals`。原清单只列了「我们觉得需要的」插件，
但官方行为树引用的远不止那些。改为完整的 Humble 集合，并注明不可裁剪。

## 尚未验证

- 真实 RPLIDAR S3 与实机底盘（本轮为 `hr_planar_sim` 仿真）
- OpenNav Docking 的 `/cmd_vel_dock` 汇入（需充电桩）
- 与 `hr_task_manager` 的任务级串联
