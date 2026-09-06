# OpenCTR 快速验证固件副本

`OpenCTR_H60V36_R750ROS_V3.61.0602_safe/` 是从 `firmware/vendor/` 复制出的验证分支，用于让当前 OpenCTR H60 硬件更安全地完成技术方案链路调试。厂商原目录保持不变。

已补充：

- 上电时 ROS 命令默认无效，目标速度归零。
- UART2 USB、UART4 TTL 或 CAN 收到合法速度帧后刷新 200 ms 倒计时。
- 倒计时到期后下位机独立把 `vx/vy/wz` 全部清零。
- UART2/UART4 速度帧必须严格为 11 字节。
- UART2/UART4 拒绝小于 5 或超过 40 字节的长度，避免接收缓冲越界。
- 非速度帧不再抢占为 ROS 控制模式。

`Robot/ax_failsafe.c` 已用宿主机 GCC 测试：上电归零、合法命令刷新、10×20 ms 后归零、非 ROS 控制不干预均通过。Keil 工程已加入该源文件。

当前虚拟机没有 Keil/Arm Compiler，尚未完成整个 STM32 工程编译，严禁直接使用旧的预编译 HEX 冒充新固件。刷写前还必须确认实物确为 OpenCTR H60 V3.6、当前底盘确为麦克纳姆轮，并在车轮悬空条件下验证。
