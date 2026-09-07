# Windows 侧：编译并刷写 OpenCTR 安全固件（提示词）

整份复制给 Windows 上的 AI 助手即可。它包含完成任务所需的全部事实，
不需要读者先了解本项目。

---

## 你的任务

在 Windows 上用 Keil MDK 编译一份 STM32 固件，刷写到机器人控制板，然后验证
一条安全行为：**上位机通信断开后，底盘必须在 200 ms 内自动归零，而不是保持
最后一帧非零速度。**

在这条行为验证通过之前，这台机器人禁止落地运动。

## 背景（为什么要做这件事）

机器人的控制板现在跑的是厂商原厂固件 OpenCTR H60 V3.61。代码审查发现它
**没有上位机命令超时归零**：ROS 侧发了一帧非零速度后如果通信中断，底盘会
一直保持那个速度跑下去。这是禁止实车运动的直接原因。

已经写好并通过宿主机测试的补丁修掉了这一条。补丁很小（184 行），只加了一个
新文件和五处调用点，**没有改动任何电机控制、运动学或 CAN 通信逻辑**。

## 工程在哪

代码在私有仓库 `github.com/JosephQ47/Home_robot`（分支 main）。克隆后：

```
firmware/vendor/OpenCTR_H60V36_R750ROS_V3.61.0602/          原厂只读副本，不要改
firmware/validation/OpenCTR_H60V36_R750ROS_V3.61.0602_safe/ 要编译的就是这个
firmware/validation/openctr_v3_61_safe.patch                可单独审查的补丁
firmware/validation/tests/test_ax_failsafe.c                宿主机测试（已通过）
```

**要打开的 Keil 工程**：
`firmware/validation/OpenCTR_H60V36_R750ROS_V3.61.0602_safe/Project/xproject.uvprojx`

## 工程参数（用于核对，不需要你改）

| 项 | 值 |
|---|---|
| 芯片 | STM32F407VETx，Cortex-M4，带 FPU |
| Flash | 512 KB @ `0x08000000` |
| RAM | 128 KB @ `0x20000000` + 64 KB CCM @ `0x10000000` |
| 晶振 | 12 MHz |
| 编译器 | ARMCC（Keil MDK 自带），**不是** GCC |
| 宏定义 | `STM32F40_41xxx, USE_STDPERIPH_DRIVER, __FPU_PRESENT=1, __TARGET_FPU_VFP, ARM_MATH_CM4, __CC_ARM, USE_USB_OTG_FS` |
| 源文件 | 94 个 .c |

工程文件已经把新增的 `Robot\ax_failsafe.c` 加进了编译列表，**不需要手工添加文件**。
如果 Keil 报找不到该文件，说明仓库没克隆完整，先检查而不是自己新建。

## 补丁做了什么（六处，都很小）

新增 `Robot/ax_failsafe.c` 与 `Robot/ax_failsafe.h`，核心逻辑：

- `AX_FAILSAFE_TIMEOUT_TICKS = 10`，调用点是 20 ms 周期 → **超时 200 ms**。
- 每收到一帧合法 ROS 速度命令，调 `AX_FAILSAFE_OnRosCommand()` 把计数器重置。
- 每 20 ms 调一次 `AX_FAILSAFE_Update20ms()`：计数器归零时把 `vx/vy/wz` 全部写 0。
- **上电后计数器初值为 0**，即上电即视为"命令已失效"，必须收到新命令才允许输出。
- 只在控制源为 ROS（`AX_FAILSAFE_CTL_ROS`）时生效；遥控器等其他控制源不受影响。

调用点插在 `Robot/ax_robot.c` 的控制循环里，位于"选择控制源"之后、
"判断运动是否开启"之前：

```c
//ROS/CAN通信断开后独立归零，禁止保持最后一帧非零速度
AX_FAILSAFE_Update20ms(ax_control_mode, &R_Vel.TG_IX, &R_Vel.TG_IY, &R_Vel.TG_IW);
```

另外三处是防御性检查，改在 `Driver/ax_uart2.c`、`Driver/ax_uart4.c`、
`Driver/ax_can.c`：速度帧严格长度检查、串口帧缓冲长度检查、阻止无关数据帧
抢占 ROS 控制源。

想逐行核对就看 `openctr_v3_61_safe.patch`，或者
`git diff firmware/vendor/... firmware/validation/...`。

## 步骤

### 1. 编译

用 Keil MDK（μVision 5）打开 `xproject.uvprojx`，Rebuild All。

- 必须 **0 Error**。有 Warning 可以接受（原厂代码本来就有），但要把 Warning
  数量记下来，和编译原厂 `firmware/vendor/` 那份对比——**新增的 Warning 才值得看**。
- 产物在 `Project/Objects/` 下的 `.hex` 或 `.axf`。

如果缺 Device Pack，装 `Keil::STM32F4xx_DFP`。

### 2. 刷写前的物理准备（不能省）

刷写会让板子复位重启。必须先做到：

1. **车轮离地**——把车架垫起来，或者拆掉轮子。
2. **电池可以立刻断开**——手能直接够到电池插头或总开关。
3. 周围没有人和障碍物。

### 3. 刷写

用 ST-Link（或板载调试器）连 SWD，Keil 里 Flash → Download。

刷写前先在 Keil 的 Debug 设置里确认识别到芯片是 STM32F407，别刷错板子。

**建议先备份原厂固件**：用 ST-Link Utility 或 STM32CubeProgrammer 把
`0x08000000` 起 512 KB 读出来存成 `.bin`，出问题能刷回去。

### 4. 验证（这一步才是目的）

刷完后，**车轮仍然离地**，按顺序做：

| # | 操作 | 期望 |
|---|---|---|
| 1 | 只上电，不接上位机 | 轮子**不转**（上电即命令失效） |
| 2 | 接上位机，发一帧非零速度 | 轮子转起来 |
| 3 | 拔掉上位机 USB（或停止发送） | 轮子在**约 200 ms 内停住**，不是继续转 |
| 4 | 重新接上并发命令 | 轮子重新转起来 |
| 5 | 切到遥控器控制 | 遥控正常，不受上述超时影响 |

**第 3 条是整件事的核心。** 它不通过就等于没做，实车运动仍须禁止。

计时不需要精确仪器，肉眼判断"松手即停"和"继续跑一段"的区别就够了；
要精确的话可以录个 60 fps 视频数帧。

### 5. 需要回报的内容

请把这几项发回来（会记进项目的 STATUS.md）：

1. 编译结果：Error 数、Warning 数；与原厂那份的 Warning 数对比。
2. 产物文件名与 SHA256。
3. 原厂固件备份是否已保存、存在哪。
4. 上面五条验证逐条的实际现象。
5. 任何与预期不符的地方——**不要美化**。第 3 条如果没停住，如实说，
   那意味着补丁没生效，需要回来查调用点。

## 安全红线

- 验证全程车轮离地，人手不离电池开关。
- 第 3 条没通过之前，**不要让机器人落地运动**。
- 不要修改 `firmware/vendor/` 下的任何文件——那是原厂只读基准，
  安全补丁的全部论证都建立在"它未被改动"这个前提上。
- 如果编译报错要靠改电机控制、运动学或 CAN 代码才能过，**停下来问**，
  不要自己改——那超出了这个补丁的范围。

## 上位机侧的配合（供参考，不用你做）

固件验证通过后，Ubuntu 侧还有三道软件门要显式打开才会真正向底盘发命令，
默认全是关的：`command_output_enabled`、`legacy_firmware_watchdog_verified`、
`bench_motion_authorized`。这是刻意设计的——固件有了断链保护，不等于软件侧
自动放行。
