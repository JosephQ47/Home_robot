# HomeRobot 上下位机协议验证草案 V1

本目录是在 PC 和主机测试中验证技术方案协议结构的草案数据字典，不修改技术方案，也不表示协议已经冻结。OpenCTR `0x50/0x10` 只作为当前硬件的临时只读兼容协议，不得与本草案混用。

## 帧格式

所有多字节整数使用小端序。`Length` 表示 Payload 字节数。CRC 使用 CRC-16/CCITT-FALSE（poly `0x1021`、init `0xFFFF`、refin/refout false、xorout `0`），覆盖 `Version` 至 Payload，不包含 SOF 和 CRC。

```text
SOF A5 5A (2) | Version (1) | MsgId (1) | Length (2) | Seq (2) |
TimestampMs (4) | Payload (N) | CRC16 (2)
```

首版协议版本为 `1`，最大 Payload 为 96 字节。接收端必须检查帧头、版本、长度、CRC、消息载荷长度、序号前进和时间戳新鲜度，全部通过后才能覆盖最新命令快照。

## 消息 ID

| 名称 | ID | 方向 | 状态 |
|---|---:|---|---|
| `CMD_MOTION` | `0x01` | 上位机 → STM32 | 草案已实现并有主机测试 |
| `CMD_MODE` | `0x02` | 上位机 → STM32 | 类型保留，模式状态机待硬件评审 |
| `HEARTBEAT` | `0x03` | 双向 | 帧级支持 |
| `STATE_FAST` | `0x81` | STM32 → 上位机 | ID 保留，字段待 IMU/电机实测冻结 |
| `STATE_SLOW` | `0x82` | STM32 → 上位机 | ID 保留，字段待安全与诊断评审 |
| `FAULT_EVENT` | `0x83` | STM32 → 上位机 | ID 保留，确认重发机制待实现 |

## `CMD_MOTION` Payload

| 偏移 | 类型 | 名称 | 单位/含义 |
|---:|---|---|---|
| 0 | `int32` | `vx_mm_s` | 前向速度，mm/s |
| 4 | `int32` | `wz_mrad_s` | 偏航角速度，mrad/s |
| 8 | `uint8` | `enable` | 仅 `1` 表示请求运动，其余值拒绝 |
| 9 | `uint8` | `reserved` | 必须为 0 |

V1 不定义 `vy`，符合四轮差速底盘边界。速度范围还必须经过下位机实测限值和斜坡限制；协议字段能表示的范围不代表允许范围。命令默认超时为 150 ms，超时后下位机独立归零。

## 尚未冻结

CAN ID、轮径、轮距、轮序、减速比、PID、最大速度/加速度/减速度、电流限制、SBUS 通道数值、急停电平、IMU 标定、状态帧量化格式均保持 `TBD`。这些值不写入默认固件。
