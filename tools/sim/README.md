# 仿真与验收工具

不需要机器人。`hr_planar_sim` 读户型、积分 `/cmd_vel`、对墙体射线投射出 `/scan`，
所以建图和真实 Nav2 都能在 PC 上完整跑通。

| 文件 | 作用 |
|---|---|
| `plan_tour.py` | 在膨胀栅格上用 A* 规划无碰撞巡游路线，逐段校验不穿墙 |
| `drive_tour.py` | 按规划路线驱动仿真底盘，带位移判据的卡死恢复 |
| `slam_bench.yaml` | 建图用的 slam_toolbox 参数 |
| `run_mapping.sh` | 仿真 + SLAM + 巡游 + 存图，一条命令建出 `maps/home1` |
| `slam_track.py` | 对照实验：比对 SLAM 位姿与仿真真值，用来判断问题在 SLAM 还是在上游 |
| `run_nav2.sh` | 拉起真实 Nav2 全栈并跑速度链验收 |
| `verify_nav2.py` | 六条判据，见 `docs/acceptance/真实Nav2速度链验收.md` |

## 建图

```bash
bash tools/sim/run_mapping.sh /tmp/hr_bench
```

## 真实 Nav2 速度链验收

```bash
bash tools/sim/run_nav2.sh /tmp/hr_bench
```

最关键的一条是 AC-N5：把阶段切到 `ZERO`，Nav2 仍在计算并持续输出 `/cmd_vel_nav`，
但 `/cmd_vel_auto` 与 `/cmd_vel` 必须双双为零。它证明安全链对**真实 Nav2** 成立，
而不只是对脚本注入的假速度成立。

## 排查经验

地图扭曲时不要先调 SLAM 参数。先用 `slam_track.py` 做对照实验：走直线、原地转、
再走直线，比对 SLAM 位姿与真值。如果误差是毫米级，问题就不在 SLAM，
而在扫描、里程计或路径 —— 本项目三次地图问题的真因分别是时间戳竞态、
路径穿墙、以及卡死判据与正常转向重叠，没有一次是 SLAM 参数。
