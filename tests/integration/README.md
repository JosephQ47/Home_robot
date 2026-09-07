# 集成测试（技术方案 §9.1 要求的 tests/integration/）

按技术方案，本目录存放：**串口回环、断链、超时和端到端测试**。

当前这些测试实际位于 `upper/tools/verify_*.py`，因为它们全部依赖 ROS 2 运行时
（启动 launch、订阅话题、驱动 Action），放在上位机工作空间内运行更自然。

| 测试 | 现在的位置 | 覆盖的方案条目 |
|---|---|---|
| Mock 全链拓扑与安全默认 | `upper/tools/verify_mock_framework.py` | 端到端 |
| 短程目标 / 跟随 / 目标丢失 / 障碍停车 | `upper/tools/verify_motion_chain.py` | 端到端 |
| 任务 Action 六类生命周期 | `upper/tools/verify_task_lifecycle.py` | 端到端 |
| 伪串口字节级收发与命令超时归零 | `upper/tools/verify_bridge_pty.py` | 串口回环、超时 |
| 目标 → UART 字节全链 | `upper/tools/verify_full_control_pty.py` | 端到端 |
| 毫米波障碍源失效安全 | `upper/tools/verify_hmmd_gate.py` | 断链、失效安全 |
| 配置接线审计 | `upper/tools/verify_config_wiring.py` | — |

**待裁决**：是把这些脚本迁到本目录（贴合方案目录结构），还是保留在
`upper/tools/` 并在此登记（贴合"依赖 ROS 运行时"的实际）。两种都说得通，
需要人拍板；在拍板前不擅自迁移，避免又一次大范围改路径。
