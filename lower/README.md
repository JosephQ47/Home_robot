# HomeRobot 下位机方案验证工程

该目录用于按《家庭服务机器人技术方案》快速验证任务划分、协议、安全状态机和控制算法。它不是对技术方案的修改，也不是已经完成的正式量产固件。目标硬件仍是方案中的大疆 C 板 STM32F407IGT6；`firmware/vendor/` 中的 OpenCTR 工程只提供实测参考。

目前已实现可在 PC 上验证的安全核心：V1 协议草案、CRC、流式解析、序号/时间戳检查、150 ms 上位机命令超时、遥控接管回中门、任务心跳安全门、差速运动学和速度斜坡。四个业务入口按方案命名为 `monitor_task`、`chassis_task`、`imu_task`、`command_task`。

板级 BSP、FreeRTOS 静态任务创建、BMI088/IST8310、C620/M3508 CAN、HT-10A SBUS、IWDG 和急停 GPIO 尚未绑定。所有对应配置保持 `TBD`，因此当前工程只生成主机测试，不会生成可刷写 HEX。

```bash
cmake -S lower -B lower/build-host
cmake --build lower/build-host
ctest --test-dir lower/build-host --output-on-failure
```

接入硬件前必须依次完成：实物 BOM/引脚核对、急停电平确认、单电机离地测试、CAN ID 和轮序确认、IMU 方向标定、IWDG 故障注入、USB 断链停车，再允许上位机发送非零速度。
