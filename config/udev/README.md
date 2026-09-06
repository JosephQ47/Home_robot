# 串口稳定命名

当前实测 USB 标识：

- `/dev/robot_mcu`：OpenCTR Type-C，`1a86:55d4`，序列号 `5B34018995`。
- `/dev/hmmd_sensor`：CH344 COMC，USB interface `04`。
- `/dev/hi3516_debug`：CH344 COMD，USB interface `06`。

安装规则需要一次管理员权限：

```bash
sudo /home/luckfox/d2lros2/Home_robot/config/udev/install_serial_rules.sh
```

之后重新插拔 USB，并检查：

```bash
ls -l /dev/robot_mcu /dev/hmmd_sensor /dev/hi3516_debug
```

规则使用当前实测 VID/PID、控制板序列号和 CH344 接口号。若更换转换器或调整物理通道，
必须重新运行 `udevadm info -q property -n /dev/ttyACM*` 核对，不能沿用旧映射。
