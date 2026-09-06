# hr_hmmd

微雪 HMMD 人体微动雷达的 ROS 2 串口接入。节点只发布人体存在、径向目标距离和
16 个距离门能量，不发布 `LaserScan`，也不承担 SLAM 或二维避障。

## 接线

使用 **3.3 V TTL** USB 转串口：`3V3→VCC`、`GND→GND`、雷达 `TX→RX`、
雷达 `RX→TX`。不要将 RS-232 电平或 5 V UART 接到雷达。默认串口为
115200、8N1。先在 VMware 中把 USB 转串口连接给 Ubuntu，然后执行：

```bash
lsusb
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
udevadm info -q property -n /dev/ttyUSB0
```

按实际枚举结果替换下面的设备路径。CH344 四路串口是现有开发板调试设备，不能
仅凭 `/dev/ttyACM*` 名称认定它是 HMMD。

## 安全实测

```bash
cd /home/luckfox/d2lros2/Home_robot/upper/src
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch hr_hmmd hmmd.launch.py \
  transport_enabled:=true port:=/dev/ttyUSB0 range_scale_m:=0.0
```

节点会发送官方的“上报模式”命令，然后解析二进制上报帧。另开终端检查：

```bash
source /opt/ros/humble/setup.bash
source /home/luckfox/d2lros2/Home_robot/upper/src/install/setup.bash
ros2 topic hz /hmmd/detection
ros2 topic echo /hmmd/detection
ros2 topic echo /diagnostics
```

`range_scale_m=0.0` 时 `range_m` 为 NaN 且 `valid=false`，`range_raw` 和原始 16 距离门能量仍会
发布。这用于避免在没有实测前猜测目标距离字段单位。把人放在 1 m、2 m、3 m 三个
已量距离处采样，确认 `range_raw` 的换算关系后再设置比例并记录证据。官方说明一个
距离门为 0.7 m，但这不等于目标距离字段必然以 0.7 m 为单位。

停止节点使用 `Ctrl-C`。节点从不发布 `/cmd_vel`，本测试不会驱动底盘。

## 无地图使用边界

- 可用：人体存在检测、靠近/离开趋势、与摄像头人体检测组合的跟随停车条件。
- 条件可用：轮速里程计和 IMU 有效、相机能提供目标方向时，做短距离局部跟随。
- 不可用：只靠 HMMD 生成二维地图、AMCL 定位、二维全局规划或可靠的全向避障。

在没有平面扫描、深度相机或成像毫米波点云时，真实底盘自主导航保持禁用。
